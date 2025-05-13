#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_capital_pool.py
Pruebas unitarias para el plugin trading_gestor_capital_pool.
"""

import pytest
import asyncio
import json
import os
from datetime import datetime, time
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.entidad_gestor_usuarios import EntidadGestorUsuarios
from corec.plugins.trading.entidad_gestor_capital import EntidadGestorCapitalPool
from corec.plugins.trading.entidad_cierre_trading import EntidadCierreTrading
from corec.plugins.trading.entidad_reloj_trading import EntidadRelojTrading

@pytest.mark.asyncio
async def test_capital_pool():
    config = {
        "canales": ["trading_usuarios", "trading_capital", "trading_clock", "trading_comandos", "alertas"],
        "estado_persistente": True,
        "persistencia_opcional": True,
        "log_level": "INFO",
        "destino_default": "trading",
        "max_users": 10,
        "min_capital_per_user": 10.0,
        "max_capital_active_pct": 0.6,
        "users_table": "users",
        "capital_pool_table": "capital_pool",
        "metrics_table": "daily_metrics",
        "vigilancia_inicio": "00:00",
        "vigilancia_fin": "03:00",
        "cierre_hora": "23:55",
        "ciclo_intervalo": 1,
        "auto_register_channels": True,
        "estado_file_usuarios": "estado_gestor_usuarios_test.json",
        "estado_file_capital": "estado_gestor_capital_test.json",
        "redis": {"host": "localhost", "port": 6379, "db": 0}
    }

    for f in ["estado_gestor_usuarios_test.json", "estado_gestor_capital_test.json"]:
        if os.path.exists(f):
            os.remove(f)

    controller = AetherionController({"id": "test-controller"})
    gestor_usuarios = EntidadGestorUsuarios(config)
    gestor_capital = EntidadGestorCapitalPool(config)
    cierre_trading = EntidadCierreTrading(config)
    reloj_trading = EntidadRelojTrading(config)

    entities = [gestor_usuarios, gestor_capital, cierre_trading, reloj_trading]
    for entity in entities:
        entity.controller = controller
        await entity.init()

    usuarios = [
        {"usuario_id": "usr_1", "capital_inicial": 100.0},
        {"usuario_id": "usr_2", "capital_inicial": 200.0}
    ]
    for user in usuarios:
        await gestor_usuarios.register_user(user["usuario_id"], user["capital_inicial"])

    assert len(gestor_capital.users) == 2
    assert gestor_capital.total_capital == 300.0
    assert abs(gestor_capital.users["usr_1"]["porcentaje_participacion"] - 1/3) < 0.01
    assert abs(gestor_capital.users["usr_2"]["porcentaje_participacion"] - 2/3) < 0.01

    await gestor_usuarios.deposit_funds("usr_1", 50.0)
    assert gestor_capital.users["usr_1"]["capital_inicial"] == 150.0
    assert gestor_capital.total_capital == 350.0

    await gestor_usuarios.withdraw_funds("usr_2", 50.0)
    assert gestor_capital.users["usr_2"]["capital_inicial"] == 150.0
    assert gestor_capital.total_capital == 300.0

    trade_id = "trade_001"
    allocations = await gestor_capital.allocate_trade(120.0, trade_id)
    assert allocations["usr_1"] == 60.0
    assert allocations["usr_2"] == 60.0
    assert gestor_capital.active_capital == 120.0

    await gestor_capital.settle_trade(trade_id, 30.0)
    assert gestor_capital.users["usr_1"]["ganancia_shadow"] == 15.0
    assert gestor_capital.users["usr_2"]["ganancia_shadow"] == 15.0
    assert gestor_capital.active_capital == 0.0

    await cierre_trading.execute_daily_close()
    assert gestor_capital.users["usr_1"]["capital_inicial"] == 165.0
    assert gestor_capital.users["usr_2"]["capital_inicial"] == 165.0
    assert gestor_capital.users["usr_1"]["ganancia_shadow"] == 0.0

    await gestor_usuarios.remove_user("usr_1")
    assert "usr_1" not in gestor_capital.users
    assert gestor_capital.total_capital == 165.0

    reloj_trading.vigilancia_inicio = time(hour=0, minute=0)
    reloj_trading.vigilancia_fin = time(hour=23, minute=59)
    await reloj_trading.check_trading_mode()
    assert reloj_trading.modo == "vigilancia"

    await asyncio.gather(*[e.shutdown() for e in entities])

    with open("estado_gestor_usuarios_test.json", "r") as f:
        usuarios_data = json.load(f)
    assert "usr_2" in usuarios_data
    assert usuarios_data["usr_2"]["status"] == "active"

    with open("estado_gestor_capital_test.json", "r") as f:
        capital_data = json.load(f)
    assert "usr_2" in capital_data
    assert capital_data["usr_2"]["capital_inicial"] == 165.0
