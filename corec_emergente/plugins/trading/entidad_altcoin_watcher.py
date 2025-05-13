#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_altcoin_watcher.py
Monitorea datos de altcoins en tiempo real usando ccxt.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadAltcoinWatcher(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_altcoin", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "altcoins": ["ALT1/USDT", "ALT2/USDT", "ALT3/USDT", "ALT4/USDT", "ALT5/USDT",
                         "ALT6/USDT", "ALT7/USDT", "ALT8/USDT", "ALT9/USDT", "ALT10/USDT"],
            "auto_register_channels": True,
            "update_interval": 60
        }
        super().__init__(id="altcoin_watcher", config=config)
        self.altcoins = config["altcoins"]
        self.update_interval = config["update_interval"]
        logger.info("[AltcoinWatcher] Inicializado para altcoins: %s", ", ".join(self.altcoins))

    async def update_altcoin_data(self, symbol: str):
        try:
            exchange = ccxt.binance()
            ticker = await exchange.fetch_ticker(symbol)
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=14)
            prices = [candle[4] for candle in ohlcv]
            rsi = self._calculate_rsi(prices)
            sma = sum(prices[-50:]) / 50 if len(prices) >= 50 else prices[-1]
            sma_signal = 1 if ticker['last'] > sma else -1
            volatilidad = (max(prices[-14:]) - min(prices[-14:])) / prices[-1] if prices else 0.02
            await self.controller.publicar_evento(
                canal="trading_altcoin",
                datos={
                    "symbol": symbol,
                    "price": ticker['last'],
                    "rsi": rsi,
                    "sma_signal": sma_signal,
                    "volatilidad": volatilidad
                },
                destino="trading"
            )
            logger.debug("[AltcoinWatcher] Datos actualizados para %s: precio=%s", symbol, ticker['last'])
            await exchange.close()
        except Exception as e:
            logger.error(f"[AltcoinWatcher] Error actualizando datos para {symbol}: {e}")

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

    async def monitorear_altcoins(self):
        while not self._shutdown:
            for symbol in self.altcoins:
                await self.update_altcoin_data(symbol)
            await asyncio.sleep(self.update_interval)

    async def init(self) -> None:
        await super().init()
        asyncio.create_task(self.monitorear_altcoins())

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_comandos" and event.datos.get("texto") == "monitorear altcoins":
                for symbol in self.altcoins:
                    await self.update_altcoin_data(symbol)
        except Exception as e:
            logger.error(f"[AltcoinWatcher] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[AltcoinWatcher] Apagado")
        await super().shutdown()
