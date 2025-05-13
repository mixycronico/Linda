#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_eth_watcher.py
Monitorea datos de ETH/USDT en tiempo real usando ccxt.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadETHWatcher(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_eth", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "auto_register_channels": True,
            "update_interval": 60
        }
        super().__init__(id="eth_watcher", config=config)
        self.update_interval = config["update_interval"]
        logger.info("[ETHWatcher] Inicializado")

    async def update_eth_data(self):
        try:
            exchange = ccxt.binance()
            ticker = await exchange.fetch_ticker("ETH/USDT")
            ohlcv = await exchange.fetch_ohlcv("ETH/USDT", timeframe='1h', limit=14)
            prices = [candle[4] for candle in ohlcv]
            rsi = self._calculate_rsi(prices)
            sma = sum(prices[-50:]) / 50 if len(prices) >= 50 else prices[-1]
            sma_signal = 1 if ticker['last'] > sma else -1
            volatilidad = (max(prices[-14:]) - min(prices[-14:])) / prices[-1] if prices else 0.02
            await self.controller.publicar_evento(
                canal="trading_eth",
                datos={
                    "symbol": "ETH/USDT",
                    "price": ticker['last'],
                    "rsi": rsi,
                    "sma_signal": sma_signal,
                    "volatilidad": volatilidad
                },
                destino="trading"
            )
            logger.info("[ETHWatcher] Datos de ETH/USDT actualizados: precio=%s, rsi=%s", ticker['last'], rsi)
            await exchange.close()
        except Exception as e:
            logger.error(f"[ETHWatcher] Error actualizando datos: {e}")

    def _calculate_rsi(self, prices):
        if len(prices) < 14:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-diff)
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        return 100 - (100 / (1 + rs))

    async def monitorear(self):
        while not self._shutdown:
            await self.update_eth_data()
            await asyncio.sleep(self.update_interval)

    async def init(self) -> None:
        await super().init()
        asyncio.create_task(self.monitorear())

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_comandos" and event.datos.get("texto") == "monitorear eth":
                await self.update_eth_data()
        except Exception as e:
            logger.error(f"[ETHWatcher] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[ETHWatcher] Apagado")
        await super().shutdown()
