#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ml_predictor.py
Pruebas unitarias para el predictor basado en el enjambre.
"""

import pytest
import asyncio
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.entidad_ml_predictor import EntidadMLPredictor
from entities.nano import NanoEntidad
from corec.nucleus import Nucleus
from corec.blocks.symbiotic import BloqueSimbiotico

@pytest.mark.asyncio
async def test_ml_predictor():
    config = {
        "canales": ["trading_strategy", "alertas"],
        "log_level": "INFO",
        "destino_default": "trading",
        "auto_register_channels": True,
        "redis": {"host": "localhost", "port": 6379, "db": 0}
    }
    controller = AetherionController({"id": "test-controller"})
    nucleus = Nucleus(config)
    predictor = EntidadMLPredictor(config)
    predictor.controller = controller
    predictor.controller.nucleus = nucleus

    # Crear un bloque simbiótico para simular predicciones
    entidades = [NanoEntidad(id=f"ent{i}", canal=nucleus.canal) for i in range(3)]
    bloque = BloqueSimbiotico(id="bloque1", entidades=entidades, canal=nucleus.canal, config=config)
    nucleus.bloques.append(bloque)
    await bloque.procesar({"precio": 50000, "rsi": 25, "sma_signal": 1, "volatilidad": 0.01, "dxy": 98})

    await predictor.manejar_evento(Event(
        canal="trading_strategy",
        datos={"texto": "ejecutar predicciones"},
        destino="trading"
    ))
    assert len(controller.eventos_publicados) > 0
    assert controller.eventos_publicados[-1]["canal"] == "trading_strategy"
    assert "predicted_price" in controller.eventos_publicados[-1]["datos"]

    await predictor.shutdown()
    await nucleus.shutdown()
