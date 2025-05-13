#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_backtesting.py
Pruebas unitarias para el backtesting con datos reales y dummy.
"""

import pytest
import asyncio
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.entidad_backtest_manager import EntidadBacktestManager

@pytest.mark.asyncio
async def test_backtest_manager():
    config = {
        "canales": ["trading_backtest", "alertas"],
        "log_level": "INFO",
        "destino_default": "trading",
        "auto_register_channels": True,
        "initial_capital": 1000,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "altcoins": ["ALT1/USDT"],
        "timeframe": "1h"
    }
    controller = AetherionController({"id": "test-controller"})
    backtest = EntidadBacktestManager(config)
    backtest.controller = controller
    await backtest.init()

    # Test con datos dummy
    await backtest.manejar_evento(Event(
        canal="trading_backtest",
        datos={"texto": "iniciar backtest", "use_real_data": False},
        destino="trading"
    ))
    assert "BTC/USDT" in backtest.historical_data
    assert len(backtest.historical_data["BTC/USDT"]) > 0
    assert "rsi" in backtest.historical_data["BTC/USDT"].columns

    # Test con datos reales (requiere conexión a Binance)
    # await backtest.manejar_evento(Event(
    #     canal="trading_backtest",
    #     datos={"texto": "iniciar backtest", "use_real_data": True},
    #     destino="trading"
    # ))
    # assert "BTC/USDT" in backtest.historical_data

    await backtest.shutdown()
