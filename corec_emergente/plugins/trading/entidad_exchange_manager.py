#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_exchange_manager.py
Gestiona operaciones en exchanges con circuit breaker, deslizamiento y fragmentación.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime, timedelta
import ccxt.async_support as ccxt
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadExchangeManager(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_exchange", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "circuit_breaker": {
                "max_failures": 3,
                "reset_timeout": 900
            },
            "auto_register_channels": True,
            "slippage_tolerance": 0.01
        }
        super().__init__(id="exchange_manager", config=config)
        self.exchange_name = config.get("exchange", "binance")
        self.modo = config.get("modo", "spot")
        self.altcoins = config.get("altcoins", [])
        self.circuit_breaker_config = config["circuit_breaker"]
        self.failure_count = 0
        self.breaker_tripped = False
        self.breaker_reset_time = None
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.leverage = config.get("leverage", 1)
        self.slippage_tolerance = config["slippage_tolerance"]
        self.slippage_history = []
        self.exchange = None
        logger.info(f"[ExchangeManager] Inicializado para {self.exchange_name} ({self.modo})")

    async def init(self) -> None:
        await super().init()
        try:
            self.exchange = getattr(ccxt, self.exchange_name)({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True
            })
            if self.modo == "futures":
                await self.exchange.set_leverage(self.leverage)
            logger.info(f"[ExchangeManager] Exchange {self.exchange_name} inicializado")
        except Exception as e:
            logger.error(f"[ExchangeManager] Error inicializando exchange: {e}")
            self.breaker_tripped = True
            self.breaker_reset_time = datetime.utcnow() + timedelta(seconds=self.circuit_breaker_config["reset_timeout"])

    async def check_circuit_breaker(self) -> bool:
        if self.breaker_tripped:
            now = datetime.utcnow()
            if now >= self.breaker_reset_time:
                self.breaker_tripped = False
                self.failure_count = 0
                self.breaker_reset_time = None
                logger.info(f"[ExchangeManager] Circuit breaker reseteado para {self.exchange_name} ({self.modo})")
                await self.controller.publicar_evento(
                    canal="alertas",
                    datos={"tipo": "circuit_breaker_reset", "exchange": self.exchange_name, "modo": self.modo},
                    destino="trading"
                )
            else:
                logger.warning(f"[ExchangeManager] Circuit breaker activo hasta {self.breaker_reset_time}")
                return False
        return True

    async def register_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.circuit_breaker_config["max_failures"]:
            self.breaker_tripped = True
            self.breaker_reset_time = datetime.utcnow() + timedelta(seconds=self.circuit_breaker_config["reset_timeout"])
            logger.error(f"[ExchangeManager] Circuit breaker activado para {self.exchange_name} ({self.modo})")
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "circuit_breaker_tripped", "exchange": self.exchange_name, "modo": self.modo},
                destino="trading"
            )

    def calculate_slippage(self, volatilidad: float, volume: float) -> float:
        base_slippage = volatilidad * 0.1
        volume_factor = max(0.1, 1000000 / volume)
        slippage = base_slippage * volume_factor * random.uniform(0.8, 1.2)
        return slippage

    async def execute_trade(self, decision):
        try:
            if not await self.check_circuit_breaker():
                return
            symbol = decision["symbol"]
            side = decision["type"]
            price = decision["price"]
            risk_per_trade = decision["risk_per_trade"]
            trade_multiplier = decision["trade_multiplier"]
            data = self.controller.nucleus.market_data.get(symbol, {})
            volatilidad = data.get("volatilidad", 0.02)
            volume = data.get("volume", 1000000)
            slippage = self.calculate_slippage(volatilidad, volume)
            actual_price = price * (1 + slippage if side == "buy" else 1 - slippage)
            slippage_percent = abs((actual_price - price) / price)
            if slippage_percent > self.slippage_tolerance:
                logger.warning(f"[ExchangeManager] Deslizamiento excede tolerancia: {slippage_percent*100:.2f}%")
                await self.controller.publicar_evento(
                    canal="alertas",
                    datos={"tipo": "slippage_exceed", "symbol": symbol, "slippage_percent": slippage_percent},
                    destino="trading"
                )
                return
            self.slippage_history.append(slippage_percent)
            bloque = self.controller.nucleus.bloques[0]
            amount = (bloque.capital * risk_per_trade * trade_multiplier) / price
            fragment_size = amount / 3
            fragments = [fragment_size] * 3
            if amount % fragment_size != 0:
                fragments[-1] += amount % fragment_size
            for i, fragment in enumerate(fragments):
                if fragment == 0:
                    continue
                order = await self.exchange.create_market_order(symbol, side, fragment)
                logger.info(f"[ExchangeManager] Fragmento {i+1}/{len(fragments)} ejecutado: {side} {fragment} {symbol} a {actual_price}")
                await self.controller.publicar_evento(
                    canal="alertas",
                    datos={"tipo": "trade_ejecutado", "order": order, "symbol": symbol, "fragment": i+1},
                    destino="trading"
                )
                await asyncio.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            await self.register_failure()
            logger.error(f"[ExchangeManager] Error ejecutando trade para {decision.get('symbol')}: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            datos = event.datos
            if event.canal == "trading_exchange" and datos.get("tipo") == "registro_exchange":
                logger.info(f"[ExchangeManager] Registrado: {datos.get('exchange')} ({datos.get('modo')})")
            elif event.canal == "trading_exchange" and datos.get("tipo") == "top_altcoins_actualizado":
                self.altcoins = datos.get("altcoins", [])
                logger.info(f"[ExchangeManager] Altcoins actualizados: {self.altcoins}")
            elif event.canal == "trading_exchange" and datos.get("tipo") == "trade_execution":
                await self.execute_trade(datos.get("decision"))
        except Exception as e:
            logger.error(f"[ExchangeManager] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        if self.exchange:
            await self.exchange.close()
            logger.info(f"[ExchangeManager] Exchange {self.exchange_name} cerrado")
        logger.info("[ExchangeManager] Apagado")
        await super().shutdown()
