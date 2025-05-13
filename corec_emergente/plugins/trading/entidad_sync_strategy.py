#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_sync_strategy.py
Implementa estrategias de trading usando el enjambre de CoreC Emergente con lógica de MomentumStrategy.
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
from collections import Counter

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
            "symbols": ["BTC/USDT", "ETH/USDT"],
            "phases": [
                {"name": "conservative", "min": 0, "max": 10000, "risk_per_trade": 0.01},
                {"name": "moderate", "min": 10000, "max": 50000, "risk_per_trade": 0.02},
                {"name": "aggressive", "min": 50000, "max": 1000000, "risk_per_trade": 0.03}
            ]
        }
        super().__init__(id="sync_strategy", config=config)
        self.capital = config["capital"]
        self.stop_loss_pct = config["stop_loss_pct"]
        self.atr_period = config["atr_period"]
        self.atr_base_threshold = config["atr_base_threshold"]
        self.performance_window = config["performance_window"]
        self.min_performance = config["min_performance"]
        self.phases = config["phases"]
        self.bloques = {}
        self.macro_data = {}
        self.market_data = {}
        self.redis = aioredis.Redis(
            host=config['redis']['host'],
            port=config['redis']['port'],
            decode_responses=True
        )
        self.pending_signals = {}
        logger.info("[SyncStrategy] Inicializado")

    def get_phase(self, capital: float) -> Dict:
        for phase in self.phases:
            if phase["min"] <= capital < phase["max"]:
                return phase
        return self.phases[-1]  # Fase agresiva por defecto para capitales altos

    async def init(self):
        await super().init()
        for symbol in self.config["symbols"] + self.config["altcoins"]:
            entidades = [NanoEntidad(id=f"ent_{symbol}_{i}", canal=self.canal) for i in range(5)]
            bloque = TradingSymbioticBlock(id=f"bloque_{symbol}", entidades=entidades, canal=self.canal, config=self.config)
            self.bloques[symbol] = bloque
            await self.controller.nucleus.registrar_bloque(bloque)
        logger.info("[SyncStrategy] %d bloques simbióticos inicializados", len(self.bloques))

    async def calculate_momentum(self, symbol: str, bloque: TradingSymbioticBlock) -> float:
        try:
            data = self.market_data.get(symbol, {})
            if not data:
                return 0.0
            macro_data = self.macro_data
            phase = self.get_phase(bloque.capital)
            carga = {
                "precio": data.get('price', 35000 if "BTC" in symbol else 2500 if "ETH" in symbol else 20),
                "rsi": data.get('rsi', 50),
                "sma_signal": data.get('sma_signal', 0),
                "volatilidad": data.get('volatilidad', 0.02),
                "dxy": macro_data.get('DXY', 100),
                "sp500": macro_data.get('SP500', 0.0),
                "volume": data.get('volume', 1000000)
            }
            await bloque.procesar(carga)
            resultados = bloque.memoria_colectiva[-len(bloque.entidades):]
            sentiment = 0.0
            emocion_dominante = Counter([r["emocion"] for r in resultados]).most_common(1)[0][0]
            if emocion_dominante == "alegría":
                sentiment += 50
            elif emocion_dominante == "estrés":
                sentiment -= 50
            elif emocion_dominante == "curiosidad":
                sentiment += 25
            if carga["rsi"] > 70:
                sentiment -= 50
            elif carga["rsi"] < 30:
                sentiment += 50
            if carga["sma_signal"] == 1:
                sentiment += 25
            elif carga["sma_signal"] == -1:
                sentiment -= 25
            sentiment += carga["sp500"] * 100  # Influencia de S&P 500
            sentiment -= carga["dxy"] / 2  # DXY fuerte reduce sentimiento
            sentiment += carga["volume"] / 1000000 * 0.1  # Volumen alto aumenta sentimiento
            is_uptrend = (carga["rsi"] < 30 and carga["sma_signal"] == 1 and emocion_dominante == "alegría")
            bloque.trade_multiplier = 3 if is_uptrend else 1
            logger.info(f"[SyncStrategy] Sentimiento para {symbol}: {sentiment}, Uptrend: {is_uptrend}")
            return sentiment
        except Exception as e:
            logger.error(f"[SyncStrategy] Error calculando momentum para {symbol}: {e}")
            return 0.0

    async def decide_trade(self, symbol: str, bloque: TradingSymbioticBlock, sentiment: float, volatilidad: float) -> str:
        phase = self.get_phase(bloque.capital)
        cycles_needed = 2 if phase["name"] in ["conservative", "moderate"] else 1
        volatility_factor = max(volatilidad / 0.01, 1.0)
        cycles_needed = max(1, int(cycles_needed / volatility_factor))
        trade_id = f"{symbol}"
        if trade_id not in self.pending_signals:
            self.pending_signals[trade_id] = {"cycles": 0, "sentiment": sentiment}
        else:
            self.pending_signals[trade_id]["cycles"] += 1
            self.pending_signals[trade_id]["sentiment"] = sentiment
        if self.pending_signals[trade_id]["cycles"] >= cycles_needed:
            threshold = 50 if phase["name"] == "conservative" else 60 if phase["name"] == "moderate" else 70
            decision = "comprar" if sentiment > threshold else "vender" if sentiment < -threshold else "mantener"
            del self.pending_signals[trade_id]
            logger.info(f"[SyncStrategy] Decisión para {symbol}: {decision} (Cycles: {cycles_needed})")
            return decision
        logger.debug(f"[SyncStrategy] Señal pendiente para {symbol}: {self.pending_signals[trade_id]['cycles']}/{cycles_needed} ciclos")
        return "pending"

    async def detect_opportunities(self) -> List[Dict]:
        opportunities = []
        for symbol, bloque in self.bloques.items():
            data = self.market_data.get(symbol, {})
            if not data:
                continue
            volatilidad = data.get('volatilidad', 0.02)
            sentiment = await self.calculate_momentum(symbol, bloque)
            decision = await self.decide_trade(symbol, bloque, sentiment, volatilidad)
            if decision in ["comprar", "vender"]:
                phase = self.get_phase(bloque.capital)
                opportunities.append({
                    "symbol": symbol,
                    "exchange": "binance",
                    "modo": "spot",
                    "strategy": "emergente",
                    "type": "buy" if decision == "comprar" else "sell",
                    "price": data.get('price', 35000 if "BTC" in symbol else 2500 if "ETH" in symbol else 20),
                    "probability": 0.8,
                    "stop_loss": data["price"] * (1 - self.stop_loss_pct) if decision == "comprar" else data["price"] * (1 + self.stop_loss_pct),
                    "risk_per_trade": phase["risk_per_trade"],
                    "trade_multiplier": bloque.trade_multiplier
                })
        return opportunities

    async def manejar_evento(self, event: Event) -> None:
        try:
            datos = event.datos
            if event.canal in ["trading_btc", "trading_eth", "trading_altcoin"]:
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
