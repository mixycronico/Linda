#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_trading_system.py
Pruebas unitarias para el sistema de trading completo, incluyendo el enjambre de CoreC Emergente y datos macro.
Simula 20 horas de trading con escenarios extremos.
"""

import pytest
import asyncio
import pandas as pd
import time
import os
from datetime import datetime
import json
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.coordinador_trading import EntidadCoordinadorTrading
from corec.plugins.trading.entidad_backtest_manager import EntidadBacktestManager
from corec.plugins.trading.entidad_ml_predictor import EntidadMLPredictor
from corec.plugins.trading.entidad_sync_strategy import EntidadSyncStrategy
from corec.plugins.trading.entidad_btc_watcher import EntidadBTCWatcher
from corec.plugins.trading.entidad_eth_watcher import EntidadETHWatcher
from corec.plugins.trading.entidad_altcoin_watcher import EntidadAltcoinWatcher
from corec.plugins.trading.entidad_trading_monitor import EntidadTradingMonitor
from corec.plugins.trading.entidad_exchange_manager import EntidadExchangeManager
from corec.plugins.trading.entidad_coordinacion_multi_nodo import EntidadCoordinacionMultiNodo
from corec.plugins.trading.entidad_exchange_configurator import EntidadExchangeConfigurator
from corec.plugins.trading.entidad_gestor_usuarios import EntidadGestorUsuarios
from corec.plugins.trading.entidad_gestor_capital import EntidadGestorCapitalPool
from corec.plugins.trading.entidad_cierre_trading import EntidadCierreTrading
from corec.plugins.trading.entidad_reloj_trading import EntidadRelojTrading
from corec.plugins.trading.entidad_alpha_vantage_sync import EntidadAlphaVantageSync
from corec.nucleus import Nucleus

@pytest.mark.asyncio
async def test_trading_system():
    # Configuración base para todas las entidades
    config = {
        "canales": [
            "trading_comandos", "trading_respuestas", "trading_backtest",
            "trading_strategy", "trading_btc", "trading_eth", "trading_altcoin",
            "trading_exchange", "trading_monitor", "trading_multi_nodo",
            "config_exchange", "trading_usuarios", "trading_capital", "trading_clock",
            "trading_macro", "alertas"
        ],
        "backtest": {
            "initial_capital": 1000,
            "start_date": "2025-04-15",
            "end_date": "2025-04-16",
            "timeframe": "1h"
        },
        "capital": 1000,
        "stop_loss_pct": 0.03,
        "btc_threshold_base": 0.01,
        "alt_threshold_base": 0.015,
        "max_capital_pct_base": 0.6,
        "multi_nodo": {
            "nodo_count": 5,
            "reassign_interval": 3600
        },
        "postgres": {
            "enabled": False,
            "host": "localhost",
            "port": 5432,
            "database": "trading_db",
            "user": "trading_user",
            "password": "trading_pass"
        },
        "redis": {
            "enabled": True,
            "host": "localhost",
            "port": 6379,
            "db": 0
        },
        "plantilla_path": "multi_exchange_config.yaml",
        "log_level": "INFO",
        "ui_mode": "headless",
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
        "altcoins": [f"ALT{i}/USDT" for i in range(1, 11)],
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "macro_api": {
            "alpha_vantage_key": "F0BH61XQ9KDFF90E",
            "coinmarketcap_key": "TU_COINMARKETCAP_API_KEY",
            "newsapi_key": "271a1e28d1ac4899a7b85684fdb13eeb",
            "macro_schedule": {
                "active_hours_start": "07:00",
                "active_hours_end": "17:00",
                "timezone": "America/New_York",
                "fetch_interval_minutes": 5
            }
        },
        "circuit_breaker": {
            "max_failures": 3,
            "reset_timeout": 900
        }
    }

    # Limpiar archivos de estado previos
    for f in ["estado_gestor_usuarios_test.json", "estado_gestor_capital_test.json"]:
        if os.path.exists(f):
            os.remove(f)

    # Inicializar núcleo y controlador
    nucleus = Nucleus(config)
    controller = AetherionController({"id": "test-controller"})
    controller.nucleus = nucleus

    # Inicializar entidades
    coordinador = EntidadCoordinadorTrading(config)
    backtest = EntidadBacktestManager(config)
    predictor = EntidadMLPredictor(config)
    strategy = EntidadSyncStrategy(config)
    btc_watcher = EntidadBTCWatcher(config)
    eth_watcher = EntidadETHWatcher(config)
    altcoin_watcher = EntidadAltcoinWatcher(config)
    monitor = EntidadTradingMonitor(config)
    multi_nodo = EntidadCoordinacionMultiNodo(config)
    configurator = EntidadExchangeConfigurator(config)
    gestor_usuarios = EntidadGestorUsuarios(config)
    gestor_capital = EntidadGestorCapitalPool(config)
    cierre_trading = EntidadCierreTrading(config)
    reloj_trading = EntidadRelojTrading(config)
    alpha_vantage = EntidadAlphaVantageSync(config)

    entities = [
        coordinador, backtest, predictor, strategy, btc_watcher, eth_watcher,
        altcoin_watcher, monitor, multi_nodo, configurator, gestor_usuarios,
        gestor_capital, cierre_trading, reloj_trading, alpha_vantage
    ]
    for entity in entities:
        entity.controller = controller
        await entity.init()

    # Registrar usuarios
    usuarios = [
        {"usuario_id": "usr_1", "capital_inicial": 500.0},
        {"usuario_id": "usr_2", "capital_inicial": 1000.0}
    ]
    for user in usuarios:
        await gestor_usuarios.register_user(user["usuario_id"], user["capital_inicial"])

    # Cargar configuración de exchanges
    await configurator.cargar_configuracion()

    # Generar datos dummy para backtesting
    await backtest.manejar_evento(Event(
        canal="trading_backtest",
        datos={"texto": "iniciar backtest", "use_real_data": False},
        destino="trading"
    ))

    # Simular datos macro
    macro_data = {
        'SP500': 4500.0,
        'Nasdaq': 14000.0,
        'DXY': 95.0,
        'Gold': 1900.0,
        'Oil': 80.0,
        'cmc': {
            'BTC': {'market_cap': 1000e9},
            'ETH': {'market_cap': 200e9},
            'SOL': {'volume_24h': 5e9},
            'ADA': {'volume_24h': 3e9},
            'XRP': {'volume_24h': 2e9}
        },
        'altcoins_volume': 10e9,
        'news_sentiment': 0.5,
        'simbolo': "fuego",
        'emocion': "alegría"
    }
    await alpha_vantage.redis.setex('market:macro', 1800, json.dumps(macro_data))
    await controller.publicar_evento(
        canal="trading_macro",
        datos=macro_data,
        destino="trading"
    )

    # Inicializar gestores de exchanges
    exchange_managers = []
    for entidad_id, info in configurator.active_exchanges.items():
        exchange_config = info["config"].copy()
        exchange_config.update({
            "exchange": info["exchange"],
            "modo": info["modo"],
            "altcoins": config["altcoins"]
        })
        manager = EntidadExchangeManager(exchange_config)
        manager.controller = controller
        await manager.init()
        exchange_managers.append(manager)

    # Asignar tareas a nodos
    altcoins = config["altcoins"]
    tasks = []
    for manager in exchange_managers:
        manager.altcoins = altcoins
        await manager.controller.publicar_evento(
            canal="trading_exchange",
            datos={"tipo": "top_altcoins_actualizado", "altcoins": altcoins},
            destino="trading"
        )
        tasks.extend([
            {"symbol": s, "exchange": manager.exchange_name, "modo": manager.modo}
            for s in config["symbols"] + altcoins
        ])

    await multi_nodo.manejar_evento(Event(
        canal="trading_multi_nodo",
        datos={"texto": "asignar tareas", "tasks": tasks},
        destino="trading"
    ))

    # Configurar simulación
    start_timestamp = pd.to_datetime("2025-04-15 00:00:00").timestamp()
    end_timestamp = start_timestamp + 20 * 3600  # 20 horas
    current_timestamp = start_timestamp
    metrics = {
        "trades": [],
        "capital_history": [1500],
        "predictions_made": 0,
        "stop_loss_triggered": 0,
        "nodo_times": [],
        "passive_mode_activations": 0,
        "decision_records": 0,
        "mutaciones_simbolicas": 0,
        "ajustes_salud": 0,
        "entrelazamientos_promedio": 0
    }

    # Simular eventos extremos
    crash_time = start_timestamp + 12 * 3600  # Caída del 30% a las 12:00

    async def simulate_nodo(bloque_id: int, nodo_tasks: List[Dict[str, str]]):
        nodo_metrics = {"trades": [], "predictions_made": 0}
        start_time = time.time()
        local_predictor = EntidadMLPredictor(config)
        local_strategy = EntidadSyncStrategy(config)
        local_predictor.controller = controller
        local_strategy.controller = controller
        await asyncio.gather(local_predictor.init(), local_strategy.init())

        for task in nodo_tasks:
            symbol = task["symbol"]
            exchange = task["exchange"]
            modo = task["modo"]
            data = backtest.historical_data.get(symbol, pd.DataFrame())
            if data.empty:
                continue
            pred = await local_predictor.predict_price(symbol, exchange, modo)
            if pred:
                nodo_metrics["predictions_made"] += 1
            opportunities = await local_strategy.detect_opportunities()
            for opp in opportunities:
                if opp["symbol"] == symbol:
                    trade_id = f"trade_{bloque_id}_{symbol}_{int(time.time())}"
                    allocations = await gestor_capital.allocate_trade(opp["price"] * 0.1, trade_id)
                    if allocations:
                        profit_loss = (pred["predicted_price"] - opp["price"]) * 0.1
                        opp["profit_loss"] = profit_loss
                        await gestor_capital.settle_trade(trade_id, profit_loss)
                        nodo_metrics["trades"].append(opp)

        await asyncio.gather(local_predictor.shutdown(), local_strategy.shutdown())
        return bloque_id, nodo_metrics, time.time() - start_time

    # Simulación de 20 horas
    while current_timestamp < end_timestamp:
        # Simular caída del 30% en la hora 12
        if crash_time <= current_timestamp < crash_time + 3600:
            for symbol in backtest.historical_data:
                backtest.historical_data[symbol]["close"] *= 0.7
                backtest.historical_data[symbol]["rsi"] = 20
                backtest.historical_data[symbol]["volatilidad"] *= 2.0
                macro_data["DXY"] = 102
                macro_data["simbolo"] = "tierra"
                macro_data["emocion"] = "estrés"
                await alpha_vantage.redis.setex('market:macro', 1800, json.dumps(macro_data))
                await controller.publicar_evento(
                    canal="trading_macro",
                    datos=macro_data,
                    destino="trading"
                )

        # Actualizar datos de mercado
        await btc_watcher.update_btc_data()
        await eth_watcher.update_eth_data()
        for symbol in altcoins:
            await altcoin_watcher.update_altcoin_data(symbol)

        # Ejecutar estrategias
        tasks = []
        for bloque_id, nodo_tasks in multi_nodo.nodo_assignments.items():
            if nodo_tasks:
                tasks.append(simulate_nodo(bloque_id, nodo_tasks))
        nodo_results = await asyncio.gather(*tasks)

        # Recolectar métricas
        for bloque_id, nodo_metrics, nodo_time in nodo_results:
            metrics["trades"].extend(nodo_metrics["trades"])
            metrics["predictions_made"] += nodo_metrics["predictions_made"]
            metrics["nodo_times"].append(nodo_time)
            metrics["decision_records"] += len(nodo_metrics["trades"])

        # Verificar stop-loss emocional
        for bloque in nucleus.bloques:
            if bloque.estres_consecutivo >= 5:
                metrics["stop_loss_triggered"] += 1

        # Verificar modo pasivo
        for symbol in backtest.historical_data:
            if strategy.bloques.get(symbol) and strategy.bloques[symbol].memoria_colectiva:
                if strategy.bloques[symbol].memoria_colectiva[-1]["emocion"] == "estrés":
                    metrics["passive_mode_activations"] += 1

        # Ejecutar estrategia
        await coordinador.manejar_evento(Event(
            canal="trading_comandos",
            datos={"texto": "ejecutar estrategia"},
            destino="trading"
        ))

        # Actualizar métricas
        metrics["capital_history"].append(gestor_capital.total_capital)
        metrics["mutaciones_simbolicas"] += sum(1 for b in nucleus.bloques for e in b.entidades if e.memoria_simbolica and "mutar" in str(e.memoria_simbolica[-1]))
        metrics["entrelazamientos_promedio"] = sum(len(e.entrelazadas) for b in nucleus.bloques for e in b.entidades) / sum(len(b.entidades) for b in nucleus.bloques) if nucleus.bloques else 0

        # Simular ajuste de salud simbólica
        if current_timestamp % 3600 == 0:
            await coordinador.manejar_evento(Event(
                canal="trading_comandos",
                datos={"texto": "evaluar_salud_simbolica"},
                destino="trading"
            ))
            metrics["ajustes_salud"] += 1

        current_timestamp += 60
        await asyncio.sleep(0.01)

    # Ejecutar cierre diario
    await cierre_trading.execute_daily_close()

    # Calcular métricas finales
    final_capital = gestor_capital.total_capital
    roi = (final_capital - 1500) / 1500 * 100
    drawdown = max(1500 - min(metrics["capital_history"]), 0) / 1500 * 100
    trades_count = len(metrics["trades"])
    sharpe_ratio = roi / drawdown if drawdown > 0 else 0
    wins = sum(1 for t in metrics["trades"] if t.get("profit_loss", 0) > 0)
    win_rate = wins / trades_count if trades_count > 0 else 0.0
    gross_profit = sum(t.get("profit_loss", 0) for t in metrics["trades"] if t.get("profit_loss", 0) > 0)
    gross_loss = sum(abs(t.get("profit_loss", 0)) for t in metrics["trades"] if t.get("profit_loss", 0) < 0)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    max_consecutive_losses = 0
    current_consecutive_losses = 0
    for t in metrics["trades"]:
        if t.get("profit_loss", 0) < 0:
            current_consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
        else:
            current_consecutive_losses = 0

    # Limpieza
    await asyncio.gather(*[e.shutdown() for e in entities + exchange_managers])
    await nucleus.shutdown()

    # Verificaciones
    assert final_capital > 0
    assert trades_count > 0
    assert metrics["predictions_made"] > 0
    assert win_rate >= 0.0
    assert profit_factor >= 0.0
    assert max_consecutive_losses >= 0
    assert metrics["stop_loss_triggered"] > 0  # Verificar stop-loss emocional
    assert metrics["passive_mode_activations"] > 0
    assert metrics["mutaciones_simbolicas"] > 0
    assert metrics["ajustes_salud"] > 0

    return {
        "roi": roi,
        "drawdown": drawdown,
        "trades_count": trades_count,
        "sharpe_ratio": sharpe_ratio,
        "predictions_made": metrics["predictions_made"],
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_consecutive_losses": max_consecutive_losses,
        "avg_nodo_time": sum(metrics["nodo_times"]) / len(metrics["nodo_times"]) if metrics["nodo_times"] else 0,
        "active_exchanges": list(configurator.active_exchanges.keys()),
        "passive_mode_activations": metrics["passive_mode_activations"],
        "decision_records": metrics["decision_records"],
        "mutaciones_simbolicas": metrics["mutaciones_simbolicas"],
        "ajustes_salud": metrics["ajustes_salud"],
        "entrelazamientos_promedio": metrics["entrelazamientos_promedio"]
    }
