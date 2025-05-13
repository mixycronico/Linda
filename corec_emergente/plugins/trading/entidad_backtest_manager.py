#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_backtest_manager.py
Gestiona backtests con datos reales de Binance vía ccxt.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadBacktestManager(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_backtest", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "initial_capital": 1000,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "auto_register_channels": True,
            "altcoins": ["ALT1/USDT", "ALT2/USDT", "ALT3/USDT", "ALT4/USDT", "ALT5/USDT",
                         "ALT6/USDT", "ALT7/USDT", "ALT8/USDT", "ALT9/USDT", "ALT10/USDT"],
            "timeframe": "1h"
        }
        super().__init__(id="backtest_manager", config=config)
        self.initial_capital = config["initial_capital"]
        self.start_date = config["start_date"]
        self.end_date = config["end_date"]
        self.altcoins = config["altcoins"]
        self.timeframe = config["timeframe"]
        self.historical_data = {}
        logger.info("[BacktestManager] Inicializado")

    async def fetch_historical_data(self, symbol: str):
        try:
            exchange = ccxt.binance()
            since = int(pd.to_datetime(self.start_date).timestamp() * 1000)
            ohlcv = await exchange.fetch_ohlcv(symbol, self.timeframe, since=since)
            data = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
            data['rsi'] = self._calculate_rsi(data['close'])
            data['sma'] = data['close'].rolling(window=50).mean()
            data['sma_signal'] = (data['close'] > data['sma']).astype(int) - (data['close'] < data['sma']).astype(int)
            data['volatilidad'] = (data['close'].rolling(window=14).max() - data['close'].rolling(window=14).min()) / data['close']
            self.historical_data[symbol] = data
            logger.info(f"[BacktestManager] Datos históricos cargados para {symbol}")
            await exchange.close()
        except Exception as e:
            logger.error(f"[BacktestManager] Error cargando datos para {symbol}: {e}")

    def _calculate_rsi(self, prices):
        if len(prices) < 14:
            return pd.Series([50.0] * len(prices), index=prices.index)
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)

    async def generate_dummy_data(self):
        symbols = ["BTC/USDT", "ETH/USDT"] + self.altcoins
        for symbol in symbols:
            data = pd.DataFrame({
                "timestamp": pd.date_range(start=self.start_date, end=self.end_date, freq=self.timeframe),
                "open": np.random.uniform(30000, 40000, 8760) if "BTC" in symbol else
                        np.random.uniform(2000, 3000, 8760) if "ETH" in symbol else
                        np.random.uniform(10, 50, 8760),
                "high": np.random.uniform(30500, 40500, 8760) if "BTC" in symbol else
                        np.random.uniform(2050, 3050, 8760) if "ETH" in symbol else
                        np.random.uniform(11, 55, 8760),
                "low": np.random.uniform(29500, 39500, 8760) if "BTC" in symbol else
                       np.random.uniform(1950, 2950, 8760) if "ETH" in symbol else
                       np.random.uniform(9, 45, 8760),
                "close": np.random.uniform(30000, 40000, 8760) if "BTC" in symbol else
                         np.random.uniform(2000, 3000, 8760) if "ETH" in symbol else
                         np.random.uniform(10, 50, 8760),
                "volume": np.random.uniform(100, 1000, 8760)
            })
            data['rsi'] = self._calculate_rsi(data['close'])
            data['sma'] = data['close'].rolling(window=50).mean()
            data['sma_signal'] = (data['close'] > data['sma']).astype(int) - (data['close'] < data['sma']).astype(int)
            data['volatilidad'] = (data['close'].rolling(window=14).max() - data['close'].rolling(window=14).min()) / data['close']
            self.historical_data[symbol] = data
        logger.info("[BacktestManager] Datos dummy generados para %s símbolos", len(symbols))

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_backtest" and event.datos.get("texto") == "iniciar backtest":
                if event.datos.get("use_real_data", False):
                    for symbol in ["BTC/USDT", "ETH/USDT"] + self.altcoins:
                        await self.fetch_historical_data(symbol)
                else:
                    await self.generate_dummy_data()
                logger.info("[BacktestManager] Backtest iniciado")
                await self.controller.publicar_evento(
                    canal="alertas",
                    datos={"tipo": "backtest_iniciado", "symbols": list(self.historical_data.keys())},
                    destino="trading"
                )
        except Exception as e:
            logger.error(f"[BacktestManager] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[BacktestManager] Apagado")
        await super().shutdown()
