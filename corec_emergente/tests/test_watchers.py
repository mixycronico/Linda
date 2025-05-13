#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_watchers.py
Pruebas unitarias para los watchers de BTC, ETH y altcoins.
"""

import pytest
import asyncio
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.entidad_btc_watcher import EntidadBTCWatcher
from corec.plugins.trading.entidad_eth_watcher import EntidadETHWatcher
from corec.plugins.trading.entidad_altcoin_watcher import EntidadAltcoinWatcher

@pytest.mark.asyncio
async def test_btc_watcher():
    config = {
        "canales": ["trading_btc", "alertas"],
        "log_level": "INFO",
        "destino_default": "trading",
        "auto_register_channels": True,
        "update_interval": 1
    }
    controller = AetherionController({"id": "test-controller"})
    watcher = EntidadBTCWatcher(config)
    watcher.controller = controller
    await watcher.init()

    await watcher.manejar_evento(Event(
        canal="trading_comandos",
        datos={"texto": "monitorear btc"},
        destino="trading"
    ))
    await asyncio.sleep(1)
    assert len(controller.eventos_publicados) > 0
    assert controller.eventos_publicados[-1]["canal"] == "trading_btc"
    await watcher.shutdown()

@pytest.mark.asyncio
async def test_eth_watcher():
    config = {
        "canales": ["trading_eth", "alertas"],
        "log_level": "INFO",
        "destino_default": "trading",
        "auto_register_channels": True,
        "update_interval": 1
    }
    controller = AetherionController({"id": "test-controller"})
    watcher = EntidadETHWatcher(config)
    watcher.controller = controller
    await watcher.init()

    await watcher.manejar_evento(Event(
        canal="trading_comandos",
        datos={"texto": "monitorear eth"},
        destino="trading"
    ))
    await asyncio.sleep(1)
    assert len(controller.eventos_publicados) > 0
    assert controller.eventos_publicados[-1]["canal"] == "trading_eth"
    await watcher.shutdown()

@pytest.mark.asyncio
async def test_altcoin_watcher():
    config = {
        "canales": ["trading_altcoin", "alertas"],
        "log_level": "INFO",
        "destino_default": "trading",
        "auto_register_channels": True,
        "altcoins": ["ALT1/USDT"],
        "update_interval": 1
    }
    controller = AetherionController({"id": "test-controller"})
    watcher = EntidadAltcoinWatcher(config)
    watcher.controller = controller
    await watcher.init()

    await watcher.manejar_evento(Event(
        canal="trading_comandos",
        datos={"texto": "monitorear altcoins"},
        destino="trading"
    ))
    await asyncio.sleep(1)
    assert len(controller.eventos_publicados) > 0
    assert controller.eventos_publicados[-1]["canal"] == "trading_altcoin"
    await watcher.shutdown()
