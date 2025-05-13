#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_strategies.py
Pruebas unitarias para las estrategias de trading basadas en el enjambre.
"""

import pytest
import asyncio
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.entidad_sync_strategy import EntidadSyncStrategy
from corec.plugins.trading.blocks.trading_symbiotic import TradingSymbioticBlock
from entities.nano import NanoEntidad

@pytest.mark.asyncio
async def test_sync_strategy():
    config = {
        "canales": ["trading_strategy", "trading_exchange", "alertas"],
        "log_level": "INFO",
        "destino_default": "trading",
        "auto_register_channels": True,
        "capital": 10000,
        "symbols": ["BTC/USDT"],
        "redis": {"host": "localhost", "port": 6379, "db": 0}
    }
    controller = AetherionController({"id": "test-controller"})
    strategy = EntidadSyncStrategy(config)
    strategy.controller = controller
    await strategy.init()

    # Simular datos de mercado
    await controller.publicar_evento(
        canal="trading_btc",
        datos={"symbol": "BTC/USDT", "price": 50000, "rsi": 25, "sma_signal": 1, "volatilidad": 0.01},
        destino="trading"
    )
    await strategy.manejar_evento(Event(
        canal="trading_strategy",
        datos={"texto": "ejecutar predicciones"},
        destino="trading"
    ))
    assert len(controller.eventos_publicados) > 0
    assert controller.eventos_publicados[-1]["canal"] == "trading_exchange"
    assert controller.eventos_publicados[-1]["datos"]["tipo"] == "trade_execution"

    # Test ajuste de salud simbólica
    await strategy.manejar_evento(Event(
        canal="trading_strategy",
        datos={"accion": "ajustar_salud", "nueva_etiqueta": "viento", "nueva_emocion": "curiosidad"},
        destino="trading"
    ))
    for bloque in strategy.bloques.values():
        for entidad in bloque.entidades:
            assert entidad.etiqueta == "viento"
            assert entidad.estado_emocional == "curiosidad"

    await strategy.shutdown()
