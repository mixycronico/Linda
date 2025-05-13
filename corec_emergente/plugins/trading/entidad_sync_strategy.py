#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_sync_strategy.py
Implementa estrategias de trading usando el enjambre de CoreC Emergente.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime
import json
import aioredis
from .blocks.trading_symbiotic import TradingSymbioticBlock
from entities.nano import NanoEntidad

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadSyncStrategy(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_strategy", "trading_exchange", "trading_alertas", "trading_altcoin", "trading_macro", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "capital": 1000,
            "stop_loss_pct": 0.03,
            "atr_period": 14,
            "atr_base_threshold": 0.005,
            "decision_history_table": "strategy_decisions",
            "performance_window": 3600,
            "min_performance": 0.01,
            "auto_register_channels": True,
            "redis": {"host": "localhost", "port": 6379, "db": 0},
            "altcoins": ["ALT1/USDT", "ALT2/USDT", "ALT3/USDT", "ALT4/USDT", "ALT5/USDT",
                         "ALT6/USDT", "ALT7/USDT", "ALT8/USDT", "ALT9/USDT", "ALT10/USDT"],
            "symbols": ["BTC/USDT", "ETH/USDT"]
        }
        super().__init__(id="sync_strategy", config=config)
        self.capital = config["capital"]
        self.stop_loss_pct = config["stop_loss_pct"]
        self.atr_period = config["atr_period"]
        self.atr_base_threshold = config["atr_base_threshold"]
        self.performance_window = config["performance_window"]
        self.min_performance = config["min_performance"]
        self.bloques = {}
        self.macro_data = {}
        self.market_data = {}
        self.redis = aioredis.Redis(
            host=config['redis']['host'],
            port=config['redis']['port'],
            decode_responses=True
        )
        logger.info("[SyncStrategy] Inicializado")

    async def init(self):
        await super().init()
        # Inicializar un bloque simbiótico por símbolo
        for symbol in self.config["symbols"] + self.config["altcoins"]:
            entidades = [NanoEntidad(id=f"ent_{symbol}_{i}", canal=self.canal) for i in range(5)]
            bloque = TradingSymbioticBlock(id=f"bloque_{symbol}", entidades=entidades, canal=self.canal, config=self.config)
            self.bloques[symbol] = bloque
            self.controller.nucleus.registrar_bloque(bloque)
        logger.info("[SyncStrategy] %d bloques simbióticos inicializados", len(self.bloques))

    async def detect_opportunities(self) -> List[Dict]:
        opportunities = []
        for symbol, bloque in self.bloques.items():
            data = self.market_data.get(symbol, {})
            if not data:
                continue
            carga = {
                "precio": data.get('price', 35000 if "BTC" in symbol else 2500 if "ETH" in symbol else 20),
                "rsi": data.get('rsi', 50),
                "sma_signal": data.get('sma_signal', 0),
                "volatilidad": data.get('volatilidad', 0.02),
                "dxy": self.macro_data.get('DXY', 100)
            }
            fitness = await bloque.procesar(carga)
            for entidad in bloque.entidades:
                if entidad.memoria_simbolica:
                    evento = entidad.memoria_simbolica[-1]
                    decision = evento["decision"]
                    if decision in ["comprar", "vender"]:
                        opportunities.append({
                            "symbol": symbol,
                            "exchange": "binance",
                            "modo": "spot",
                            "strategy": "emergente",
                            "type": "buy" if decision == "comprar" else "sell",
                            "price": carga["precio"],
                            "probability": 0.8,
                            "stop_loss": carga["precio"] * (1 - self.stop_loss_pct) if decision == "comprar" else carga["precio"] * (1 + self.stop_loss_pct),
                            "fitness": fitness
                        })
        return opportunities

    async def manejar_evento(self, event: Event) -> None:
        try:
            datos = event.datos
            if event.canal == "trading_btc" or event.canal == "trading_eth" or event.canal == "trading_altcoin":
                self.market_data[datos["symbol"]] = datos
                logger.debug("[SyncStrategy] Datos de mercado actualizados para %s", datos["symbol"])
            elif event.canal == "trading_macro":
                self.macro_data = datos
                logger.info("[SyncStrategy] Datos macro recibidos: %s", datos)
            elif event.canal == "trading_strategy" and datos.get("texto") == "ejecutar predicciones":
                opportunities = await self.detect_opportunities()
                for opp in opportunities:
                    await self.controller.publicar_evento(
                        canal="trading_exchange",
                        datos={"tipo": "trade_execution", "decision": opp},
                        destino="trading"
                    )
                    logger.info("[SyncStrategy] Oportunidad detectada: %s", opp)
            elif event.canal == "trading_strategy" and datos.get("accion") == "ajustar_salud":
                for bloque in self.bloques.values():
                    for entidad in bloque.entidades:
                        entidad.mutar(datos["nueva_etiqueta"], datos["nueva_emocion"])
                logger.info("[SyncStrategy] Salud simbólica ajustada a %s con emoción %s", datos["nueva_etiqueta"], datos["nueva_emocion"])
        except Exception as e:
            logger.error(f"[SyncStrategy] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        if self.redis:
            await self.redis.close()
            logger.info("[SyncStrategy] Desconectado de Redis")
        logger.info("[SyncStrategy] Apagado")
        await super().shutdown()
