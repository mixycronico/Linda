#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_exchange_manager.py
Gestiona operaciones en exchanges con circuit breaker y soporte para ccxt.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime, timedelta
import ccxt.async_support as ccxt

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
            "exchange": "binance",
            "modo": "spot"
        }
        super().__init__(id=f"exchange_manager_{config['exchange']}_{config['modo']}", config=config)
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
            await self.register_failure()

    async def check_circuit_breaker(self) -> bool:
        try:
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
        except Exception as e:
            logger.error(f"[ExchangeManager] Error verificando circuit breaker: {e}")
            return False

    async def register_failure(self) -> None:
        try:
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
        except Exception as e:
            logger.error(f"[ExchangeManager] Error registrando fallo: {e}")

    async def execute_trade(self, decision):
        try:
            if not await self.check_circuit_breaker():
                return
            symbol = decision["symbol"]
            side = decision["type"]
            price = decision["price"]
            amount = (self.controller.nucleus.bloques[0].capital * 0.1) / price
            order = await self.exchange.create_market_order(symbol, side, amount)
            trade_id = f"trade_{symbol}_{int(time.time())}"
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "allocate_trade", "trade_amount": amount * price, "trade_id": trade_id},
                destino="trading"
            )
            logger.info(f"[ExchangeManager] Trade ejecutado: {side} {amount} {symbol} a {price} en {self.exchange_name} ({self.modo})")
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "trade_ejecutado", "order": order, "trade_id": trade_id},
                destino="trading"
            )
        except Exception as e:
            await self.register_failure()
            logger.error(f"[ExchangeManager] Error ejecutando trade: {e}")

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
        try:
            if hasattr(self, 'exchange'):
                await self.exchange.close()
            logger.info("[ExchangeManager] Apagado")
            await super().shutdown()
        except Exception as e:
            logger.error(f"[ExchangeManager] Error apagando: {e}")
