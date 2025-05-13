#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_coordinador_trading.py
Pruebas unitarias para el coordinador de trading.
"""

import pytest
import asyncio
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.coordinador_trading import EntidadCoordinadorTrading

@pytest.mark.asyncio
async def test_coordinador_trading():
    config = {
        "canales": ["trading_comandos", "trading_respuestas", "alertas"],
        "log_level": "INFO",
        "destino_default": "trading",
        "auto_register_channels": True
    }
    controller = AetherionController({"id": "test-controller"})
    coordinador = EntidadCoordinadorTrading(config)
    coordinador.controller = controller
    await coordinador.init()

    # Test comando "mostrar estado trading"
    await coordinador.manejar_evento(Event(
        canal="trading_comandos",
        datos={"texto": "mostrar estado trading"},
        destino="trading"
    ))
    assert len(controller.eventos_publicados) > 0
    assert controller.eventos_publicados[-1]["canal"] == "trading_monitor"

    # Test comando "evaluar_salud_simbolica"
    await coordinador.manejar_evento(Event(
        canal="trading_comandos",
        datos={"texto": "evaluar_salud_simbolica"},
        destino="trading"
    ))
    assert len(controller.eventos_publicados) > 1
    assert controller.eventos_publicados[-1]["canal"] == "trading_strategy"

    await coordinador.shutdown()
