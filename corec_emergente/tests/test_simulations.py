#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_simulations.py
Simulaciones para validar la lógica de trading de CoreC Emergente.
"""

import pytest
import asyncio
import logging
import random
from datetime import datetime, timedelta
from corec.controlador.aetherion_controller import AetherionController
from corec.plugins.trading.coordinador_trading import EntidadCoordinadorTrading
from corec.plugins.trading.entidad_backtest_manager import EntidadBacktestManager
from corec.plugins.trading.entidad_sync_strategy import EntidadSyncStrategy
from corec.plugins.trading.entidad_exchange_manager import EntidadExchangeManager
from corec.plugins.trading.entidad_gestor_usuarios import EntidadGestorUsuarios
from corec.plugins.trading.entidad_gestor_capital import EntidadGestorCapitalPool
from corec.plugins.trading.entidad_cierre_trading import EntidadCierreTrading
from corec.plugins.trading.entidad_reloj_trading import EntidadRelojTrading
from corec.plugins.trading.entidad_alpha_vantage_sync import EntidadAlphaVantageSync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def simulate_market(controller, scenario, hours=720):
    """Simula un escenario de mercado durante un número de horas."""
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "XRP/USDT"]
    macro_data = {
        "DXY": 100.0,
        "SP500": 0.0,
        "Nasdaq": 0.0,
        "Gold": 0.0,
        "Oil": 0.0,
        "altcoins_volume": 1000000,
        "fed_rate_change": 0.0
    }
    market_data = {s: {"price": 50000 if "BTC" in s else 3000 if "ETH" in s else 50, "rsi": 50, "sma_signal": 0, "volatilidad": 0.01, "volume": 1000000, "prices": [50000 if "BTC" in s else 3000 if "ETH" in s else 50] * 50} for s in symbols}
    trades = []
    api_failures = 0

    for hour in range(hours):
        # Ajustar datos según escenario
        if scenario == "stable":
            for s in symbols:
                market_data[s]["price"] *= random.uniform(0.98, 1.02)
                market_data[s]["rsi"] = random.uniform(40, 60)
                market_data[s]["volatilidad"] = 0.01
                market_data[s]["prices"].append(market_data[s]["price"])
                market_data[s]["prices"] = market_data[s]["prices"][-50:]
            macro_data["DXY"] += random.uniform(-0.1, 0.1)
            macro_data["SP500"] = random.uniform(-0.005, 0.005)
        elif scenario == "bullish":
            for s in symbols:
                market_data[s]["price"] *= random.uniform(1.02, 1.05)
                market_data[s]["rsi"] = random.uniform(60, 80)
                market_data[s]["volatilidad"] = 0.05
                market_data[s]["prices"].append(market_data[s]["price"])
                market_data[s]["prices"] = market_data[s]["prices"][-50:]
            macro_data["DXY"] -= random.uniform(0.05, 0.1)
            macro_data["SP500"] = random.uniform(0.01, 0.02)
            macro_data["fed_rate_change"] = -0.25 if random.random() < 0.1 else 0.0
        elif scenario == "crash":
            for s in symbols:
                market_data[s]["price"] *= random.uniform(0.85, 0.95) if hour < 12 else random.uniform(0.98, 1.02)
                market_data[s]["rsi"] = random.uniform(20, 40)
                market_data[s]["volatilidad"] = 0.1 if hour < 12 else 0.02
                market_data[s]["prices"].append(market_data[s]["price"])
                market_data[s]["prices"] = market_data[s]["prices"][-50:]
            macro_data["DXY"] += random.uniform(0.1, 0.2)
            macro_data["SP500"] = random.uniform(-0.05, -0.02)
            macro_data["fed_rate_change"] = 0.25 if hour == 0 else 0.0
        elif scenario == "volatile":
            # Simular período volátil (inspirado en halving)
            if hour < 240:  # Pre-halving (10 días): Subida
                for s in symbols:
                    market_data[s]["price"] *= random.uniform(1.01, 1.03)
                    market_data[s]["rsi"] = random.uniform(60, 75)
                    market_data[s]["volatilidad"] = 0.04
                    market_data[s]["prices"].append(market_data[s]["price"])
                    market_data[s]["prices"] = market_data[s]["prices"][-50:]
                macro_data["DXY"] -= random.uniform(0.02, 0.05)
                macro_data["SP500"] = random.uniform(0.005, 0.01)
            elif hour < 360:  # Post-halving (5 días): Corrección
                for s in symbols:
                    market_data[s]["price"] *= random.uniform(0.90, 0.95)
                    market_data[s]["rsi"] = random.uniform(25, 40)
                    market_data[s]["volatilidad"] = 0.06
                    market_data[s]["prices"].append(market_data[s]["price"])
                    market_data[s]["prices"] = market_data[s]["prices"][-50:]
                macro_data["DXY"] += random.uniform(0.05, 0.1)
                macro_data["SP500"] = random.uniform(-0.02, -0.01)
                macro_data["fed_rate_change"] = 0.25 if hour == 240 else 0.0
            else:  # Recuperación (15 días)
                for s in symbols:
                    market_data[s]["price"] *= random.uniform(1.00, 1.02)
                    market_data[s]["rsi"] = random.uniform(45, 55)
                    market_data[s]["volatilidad"] = 0.02
                    market_data[s]["prices"].append(market_data[s]["price"])
                    market_data[s]["prices"] = market_data[s]["prices"][-50:]
                macro_data["DXY"] -= random.uniform(0.01, 0.03)
                macro_data["SP500"] = random.uniform(0.0, 0.005)
        elif scenario == "stress":
            for s in symbols:
                market_data[s]["price"] *= random.uniform(0.95, 1.05)
                market_data[s]["rsi"] = random.uniform(30, 70)
                market_data[s]["volatilidad"] = random.uniform(0.02, 0.08)
                market_data[s]["prices"].append(market_data[s]["price"])
                market_data[s]["prices"] = market_data[s]["prices"][-50:]
            macro_data["DXY"] += random.uniform(-0.2, 0.2)
            macro_data["SP500"] = random.uniform(-0.02, 0.02)
            # Simular fallos de API
            if random.random() < 0.2:
                api_failures += 1
                continue

        # Publicar datos de mercado
        for s in symbols:
            await controller.publicar_evento(
                canal="trading_btc" if "BTC" in s else "trading_eth" if "ETH" in s else "trading_altcoin",
                datos=market_data[s],
                destino="trading"
            )
        await controller.publicar_evento(
            canal="trading_macro",
            datos=macro_data,
            destino="trading"
        )

        # Ejecutar estrategia
        await controller.publicar_evento(
            canal="trading_comandos",
            datos={"texto": "ejecutar estrategia"},
            destino="trading"
        )

        # Simular micro-ciclo cada 6 horas
        if hour % 6 == 0:
            await controller.publicar_evento(
                canal="trading_clock",
                datos={"texto": "micro_cycle"},
                destino="trading"
            )

        # Recolectar trades
        for bloque in controller.nucleus.bloques:
            for trade in bloque.memoria_colectiva:
                if trade["decision"] in ["comprar", "vender", "cerrar"]:
                    trades.append(trade)

        await asyncio.sleep(0.1)  # Simular 1 hora

    # Calcular métricas
    metrics = {
        "total_trades": len(trades),
        "win_rate": sum(1 for t in trades if t.get("profit", 0) > 0) / len(trades) if trades else 0.0,
        "profit_factor": sum(t["profit"] for t in trades if t.get("profit", 0) > 0) / sum(-t["profit"] for t in trades if t.get("profit", 0) < 0) if any(t.get("profit", 0) < 0 for t in trades) else float('inf'),
        "roi": sum(t.get("profit", 0) for t in trades) / 12000 * 100,
        "sharpe_ratio": calculate_sharpe_ratio(trades),
        "max_drawdown": calculate_max_drawdown(trades),
        "mutaciones": sum(len(e.memoria_simbolica) for b in controller.nucleus.bloques for e in b.entidades),
        "entrelazamientos": sum(len(e.entrelazadas) for b in controller.nucleus.bloques for e in b.entidades) / sum(len(b.entidades) for b in controller.nucleus.bloques) if sum(len(b.entidades) for b in controller.nucleus.bloques) > 0 else 0,
        "api_failures": api_failures
    }
    return metrics

def calculate_sharpe_ratio(trades):
    if len(trades) < 2:
        return 0.0
    returns = [t.get("profit", 0) / 12000 for t in trades]
    mean_return = sum(returns) / len(returns)
    std_return = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
    return mean_return / std_return * (365 ** 0.5) if std_return != 0 else 0.0

def calculate_max_drawdown(trades):
    if not trades:
        return 0.0
    cumulative = [0]
    for trade in trades:
        cumulative.append(cumulative[-1] + trade.get("profit", 0))
    peak = max(cumulative)
    drawdown = [(peak - c) / peak for c in cumulative]
    return max(drawdown) if drawdown else 0.0

@pytest.mark.asyncio
async def test_simulation_stable():
    controller = AetherionController({"id": "test-controller"})
    await setup_controller(controller)
    metrics = await simulate_market(controller, "stable")
    logger.info(f"Stable Market Metrics: {metrics}")
    assert metrics["roi"] > 0, "ROI debe ser positivo en mercado estable"
    assert metrics["win_rate"] >= 0.5, "Win rate debe ser al menos 50%"

@pytest.mark.asyncio
async def test_simulation_bullish():
    controller = AetherionController({"id": "test-controller"})
    await setup_controller(controller)
    metrics = await simulate_market(controller, "bullish")
    logger.info(f"Bullish Market Metrics: {metrics}")
    assert metrics["roi"] > 10, "ROI debe ser alto en mercado alcista"
    assert metrics["win_rate"] >= 0.7, "Win rate debe ser alto"

@pytest.mark.asyncio
async def test_simulation_crash():
    controller = AetherionController({"id": "test-controller"})
    await setup_controller(controller)
    metrics = await simulate_market(controller, "crash", hours=24)
    logger.info(f"Crash Market Metrics: {metrics}")
    assert metrics["max_drawdown"] < 0.2, "Drawdown debe ser controlado"
    assert metrics["total_trades"] < 50, "Menos trades durante caída"

@pytest.mark.asyncio
async def test_simulation_volatile():
    controller = AetherionController({"id": "test-controller"})
    await setup_controller(controller)
    metrics = await simulate_market(controller, "volatile")
    logger.info(f"Volatile Market Metrics: {metrics}")
    assert metrics["roi"] > 5, "ROI debe ser positivo en período volátil"
    assert metrics["win_rate"] >= 0.6, "Win rate debe ser razonable"
    assert metrics["max_drawdown"] < 0.3, "Drawdown debe ser controlado"

@pytest.mark.asyncio
async def test_simulation_stress():
    controller = AetherionController({"id": "test-controller"})
    await setup_controller(controller)
    metrics = await simulate_market(controller, "stress", hours=2000)
    logger.info(f"Stress Test Metrics: {metrics}")
    assert metrics["api_failures"] > 0, "Deben detectarse fallos de API"
    assert metrics["roi"] != 0, "Sistema debe seguir operando"
    assert metrics["mutaciones"] < 10000, "Mutaciones deben ser limitadas"

async def setup_controller(controller):
    config = {
        "canales": ["trading_comandos", "trading_respuestas", "trading_backtest", "trading_strategy",
                    "trading_btc", "trading_eth", "trading_altcoin", "trading_exchange",
                    "trading_monitor", "trading_multi_nodo", "config_exchange", "trading_usuarios",
                    "trading_capital", "trading_clock", "trading_macro", "alertas"],
        "redis": {"host": "localhost", "port": 6379, "db": 0},
        "auto_register_channels": True
    }
    coordinador = EntidadCoordinadorTrading(config)
    backtest = EntidadBacktestManager(config)
    strategy = EntidadSyncStrategy(config)
    exchange = EntidadExchangeManager(config)
    usuarios = EntidadGestorUsuarios(config)
    capital = EntidadGestorCapitalPool(config)
    cierre = EntidadCierreTrading(config)
    reloj = EntidadRelojTrading(config)
    alpha = EntidadAlphaVantageSync(config)

    controller.registrar_entidad(coordinador)
    controller.registrar_entidad(backtest)
    controller.registrar_entidad(strategy)
    controller.registrar_entidad(exchange)
    controller.registrar_entidad(usuarios)
    controller.registrar_entidad(capital)
    controller.registrar_entidad(cierre)
    controller.registrar_entidad(reloj)
    controller.registrar_entidad(alpha)

    await coordinador.init()
    await backtest.init()
    await strategy.init()
    await exchange.init()
    await usuarios.init()
    await capital.init()
    await cierre.init()
    await reloj.init()
    await alpha.init()

    for i in range(10):  # 10 usuarios
        await controller.publicar_evento(
            canal="trading_comandos",
            datos={"texto": f"register_user user_{i} 1200"},
            destino="trading"
        )
