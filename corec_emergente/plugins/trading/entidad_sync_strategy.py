#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_sync_strategy.py
Implementa estrategias de trading emergentes usando el enjambre de CoreC Emergente, con lógica de momentum.
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
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.05,
            "atr_period": 14,
            "atr_base_threshold": 0.005,
            "decision_history_table": "strategy_decisions",
            "performance_window": 3600,
            "min_performance": 0.01,
            "auto_register_channels": True,
            "redis": {"host": "localhost", "port": 6379, "db": 0},
            "altcoins": ["SOL/USDT", "ADA/USDT", "XRP/USDT"],
            "symbols": ["BTC/USDT", "ETH/USDT"],
            "phases": [
                {"name": "conservative", "min": 0, "max": 10000, "risk_per_trade": 0.01, "rsi_buy": 75, "rsi_sell": 25, "cycles_needed": 2},
                {"name": "moderate", "min": 10000, "max": 50000, "risk_per_trade": 0.02, "rsi_buy": 70, "rsi_sell": 30, "cycles_needed": 1},
                {"name": "aggressive", "min": 50000, "max": 1000000, "risk_per_trade": 0.03, "rsi_buy": 65, "rsi_sell": 35, "cycles_needed": 1}
            ],
            "memoria_simbolica_max": 10
        }
        super().__init__(id="sync_strategy", config=config)
        self.capital = config["capital"]
        self.stop_loss_pct = config["stop_loss_pct"]
        self.take_profit_pct = config["take_profit_pct"]
        self.atr_period = config["atr_period"]
        self.atr_base_threshold = config["atr_base_threshold"]
        self.performance_window = config["performance_window"]
        self.min_performance = config["min_performance"]
        self.phases = config["phases"]
        self.memoria_simbolica_max = config["memoria_simbolica_max"]
        self.bloques = {}
        self.macro_data = {}
        self.market_data = {}
        self.pending_signals = {}
        self.redis = aioredis.Redis(
            host=config['redis']['host'],
            port=config['redis']['port'],
            decode_responses=True
        )
        logger.info("[SyncStrategy] Inicializado")

    def get_phase(self, capital: float) -> Dict:
        for phase in self.phases:
            if phase["min"] <= capital < phase["max"]:
                return phase
        return self.phases[-1]

    async def init(self):
        await super().init()
        for symbol in self.config["symbols"] + self.config["altcoins"]:
            entidades = [NanoEntidad(id=f"ent_{symbol}_{i}", canal=self.canal) for i in range(5)]
            bloque = TradingSymbioticBlock(id=f"bloque_{symbol}", entidades=entidades, canal=self.canal, config=self.config)
            self.bloques[symbol] = bloque
            await self.controller.nucleus.registrar_bloque(bloque)
        logger.info("[SyncStrategy] %d bloques simbióticos inicializados", len(self.bloques))

    def calculate_macd(self, prices: List[float]) -> float:
        if len(prices) < 26:
            return 0.0
        exp12 = sum(prices[-12:]) / 12
        exp26 = sum(prices[-26:]) / 26
        return exp12 - exp26

    async def detect_opportunities(self) -> List[Dict]:
        opportunities = []
        for symbol, bloque in self.bloques.items():
            data = self.market_data.get(symbol, {})
            if not data:
                continue
            prices = data.get('prices', [data.get('price', 35000)] * 50)
            phase = self.get_phase(bloque.capital)
            carga = {
                "precio": data.get('price', 35000 if "BTC" in symbol else 2500 if "ETH" in symbol else 20),
                "rsi": data.get('rsi', 50),
                "sma_signal": data.get('sma_signal', 0),
                "volatilidad": data.get('volatilidad', 0.02),
                "dxy": self.macro_data.get('DXY', 100),
                "sp500": self.macro_data.get('SP500', 0.0),
                "macd": self.calculate_macd(prices)
            }
            fitness = await bloque.procesar(carga)
            trade_id = f"binance:{symbol}"

            sentiment = 0.0
            if carga["rsi"] > phase["rsi_buy"]:
                sentiment -= 50
            elif carga["rsi"] < phase["rsi_sell"]:
                sentiment += 50
            if carga["macd"] > 0:
                sentiment += 25
            elif carga["macd"] < 0:
                sentiment -= 25
            sentiment += (carga["sp500"] + self.macro_data.get("Nasdaq", 0.0) - carga["dxy"] + self.macro_data.get("Gold", 0.0) + self.macro_data.get("Oil", 0.0)) * 100
            sentiment += self.macro_data.get("altcoins_volume", 0) / 1000000 * 0.1

            if trade_id not in self.pending_signals:
                self.pending_signals[trade_id] = {"cycles": 0, "sentiment": sentiment, "decision": None}
            else:
                self.pending_signals[trade_id]["cycles"] += 1
                self.pending_signals[trade_id]["sentiment"] = sentiment

            if self.pending_signals[trade_id]["cycles"] >= phase["cycles_needed"]:
                threshold = 50 if phase["name"] == "conservative" else 60 if phase["name"] == "moderate" else 70
                decision = "comprar" if sentiment > threshold else "vender" if sentiment < -threshold else "mantener"
                self.pending_signals[trade_id]["decision"] = decision
                del self.pending_signals[trade_id]
            else:
                decision = "pending"
                logger.debug(f"[SyncStrategy] Señal pendiente para {trade_id}: {self.pending_signals[trade_id]['cycles']}/{phase['cycles_needed']} ciclos")
                continue

            trade_multiplier = 1
            if decision == "comprar" and bloque.memoria_colectiva:
                emocion_dominante = Counter([e["emocion"] for e in bloque.memoria_colectiva]).most_common(1)[0][0]
                if emocion_dominante == "alegría" and carga["rsi"] < phase["rsi_sell"] + 5:
                    trade_multiplier = 3

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
                    "take_profit": carga["precio"] * (1 + self.take_profit_pct) if decision == "comprar" else carga["precio"] * (1 - self.take_profit_pct),
                    "trade_multiplier": trade_multiplier,
                    "fitness": fitness,
                    "risk_per_trade": phase["risk_per_trade"]
                })

            # Limitar memoria simbólica
            for entidad in bloque.entidades:
                if len(entidad.memoria_simbolica) > self.memoria_simbolica_max:
                    entidad.memoria_simbolica = entidad.memoria_simbolica[-self.memoria_simbolica_max:]

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
