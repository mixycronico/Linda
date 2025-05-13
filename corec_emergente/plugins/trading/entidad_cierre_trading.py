#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_cierre_trading.py
Ejecuta el cierre diario a las 23:59, aplicando resultados y consolidando métricas avanzadas.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime, time
import asyncpg
import plotly.graph_objects as go
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadCierreTrading(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_comandos", "trading_capital", "trading_clock", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "cierre_hora": "23:59",
            "metrics_table": "daily_metrics",
            "postgres": {
                "enabled": False,
                "host": "localhost",
                "port": 5432,
                "database": "trading_db",
                "user": "trading_user",
                "password": "trading_pass"
            },
            "auto_register_channels": True,
            "crash_threshold": -0.2,
            "stress_threshold": 0.5,
            "micro_cycle_profit_threshold": 0.05
        }
        super().__init__(id="cierre_trading", config=config)
        self.cierre_hora = time.fromisoformat(config["cierre_hora"])
        self.metrics_table = config["metrics_table"]
        self.postgres_config = config["postgres"]
        self.crash_threshold = config["crash_threshold"]
        self.stress_threshold = config["stress_threshold"]
        self.micro_cycle_profit_threshold = config["micro_cycle_profit_threshold"]
        self.is_paused = False
        self.recovery_capital_percentage = 0.1
        self.crash_count = 0
        self.crash_duration = 0
        self.db_pool = None
        self.scheduler = AsyncIOScheduler()
        self.trades_history = []
        logger.info("[CierreTrading] Inicializado")

    async def init(self) -> None:
        await super().init()
        if self.postgres_config.get("enabled"):
            try:
                self.db_pool = await asyncpg.create_pool(
                    host=self.postgres_config["host"],
                    port=self.postgres_config["port"],
                    database=self.postgres_config["database"],
                    user=self.postgres_config["user"],
                    password=self.postgres_config["password"]
                )
                logger.info("[CierreTrading] Conectado a PostgreSQL")
            except Exception as e:
                logger.error(f"[CierreTrading] Error conectando a PostgreSQL: {e}")
        self.scheduler.start()
        h, m = map(int, self.cierre_hora.strftime("%H:%M").split(":"))
        self.scheduler.add_job(
            self.execute_daily_close,
            'cron',
            hour=h,
            minute=m,
            id='daily_close',
            replace_existing=True
        )
        self.scheduler.add_job(
            self.handle_market_crash,
            'interval',
            seconds=60,
            id='market_crash',
            replace_existing=True
        )
        self.scheduler.add_job(
            self.micro_cycle,
            'interval',
            hours=6,
            id='micro_cycle',
            replace_existing=True
        )
        logger.info("[CierreTrading] Scheduler iniciado para cierre diario, micro-ciclos, y manejo de caídas")

    async def calculate_advanced_metrics(self) -> Dict:
        try:
            metrics = {
                "total_capital": 0.0,
                "active_capital": 0.0,
                "users_count": 0,
                "trades_count": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_consecutive_losses": 0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0
            }
            if not self.postgres_config.get("enabled") or not self.db_pool:
                return metrics

            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT outcome
                    FROM strategy_decisions
                    WHERE timestamp > NOW() - INTERVAL '1 day'
                    """
                )
                trades = [row["outcome"] for row in rows]
                trades_count = len(trades)
                wins = sum(1 for t in trades if t > 0)
                win_rate = wins / trades_count if trades_count > 0 else 0.0
                gross_profit = sum(t for t in trades if t > 0)
                gross_loss = sum(abs(t) for t in trades if t < 0)
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                max_consecutive_losses = 0
                current_consecutive_losses = 0
                for t in trades:
                    if t < 0:
                        current_consecutive_losses += 1
                        max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
                    else:
                        current_consecutive_losses = 0
                sharpe_ratio = self.calculate_sharpe_ratio()
                max_drawdown = self.calculate_max_drawdown()
                metrics.update({
                    "total_capital": sum(b.capital + b.posicion * b.memoria_colectiva[-1]["precio"] for b in self.controller.nucleus.bloques if b.memoria_colectiva),
                    "active_capital": sum(u["capital_disponible"] for u in self.controller.gestor_capital.users.values()),
                    "users_count": len(self.controller.gestor_capital.users),
                    "trades_count": trades_count,
                    "win_rate": win_rate,
                    "profit_factor": profit_factor,
                    "max_consecutive_losses": max_consecutive_losses,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown": max_drawdown
                })
            return metrics
        except Exception as e:
            logger.error(f"[CierreTrading] Error calculando métricas avanzadas: {e}")
            return metrics

    def calculate_sharpe_ratio(self):
        if len(self.trades_history) < 2:
            return 0.0
        returns = [trade["profit"] / self.controller.nucleus.bloques[0].capital for trade in self.trades_history]
        mean_return = sum(returns) / len(returns)
        std_return = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
        if std_return == 0:
            return 0.0
        return mean_return / std_return * (365 ** 0.5)  # Ajustado para criptomonedas (365 días)

    def calculate_max_drawdown(self):
        if len(self.trades_history) < 2:
            return 0.0
        cumulative = [0]
        for trade in self.trades_history:
            cumulative.append(cumulative[-1] + trade["profit"])
        peak = max(cumulative)
        drawdown = [(peak - c) / peak for c in cumulative]
        return max(drawdown) if drawdown else 0.0

    async def save_metrics_to_db(self, metrics: Dict) -> None:
        if not self.postgres_config.get("enabled") or not self.db_pool:
            return
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO daily_metrics (total_capital, active_capital, users_count, trades_count, 
                                               win_rate, profit_factor, max_consecutive_losses, sharpe_ratio, max_drawdown, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    metrics.get("total_capital", 0.0), metrics.get("active_capital", 0.0),
                    metrics.get("users_count", 0), metrics.get("trades_count", 0),
                    metrics.get("win_rate", 0.0), metrics.get("profit_factor", 0.0),
                    metrics.get("max_consecutive_losses", 0), metrics.get("sharpe_ratio", 0.0),
                    metrics.get("max_drawdown", 0.0), datetime.utcnow()
                )
            logger.debug("[CierreTrading] Métricas guardadas en PostgreSQL")
        except Exception as e:
            logger.error(f"[CierreTrading] Error guardando métricas: {e}")

    async def generate_roi_plot(self, now):
        try:
            dates = []
            daily_roi = []
            current_date = None
            daily_profit = 0
            for trade in self.trades_history:
                trade_date = datetime.fromisoformat(trade["timestamp"]).date()
                if current_date is None:
                    current_date = trade_date
                if trade_date != current_date:
                    dates.append(current_date)
                    daily_roi.append((daily_profit / self.controller.nucleus.bloques[0].capital) * 100)
                    daily_profit = 0
                    current_date = trade_date
                daily_profit += trade["profit"]
            if daily_profit != 0:
                dates.append(current_date)
                daily_roi.append((daily_profit / self.controller.nucleus.bloques[0].capital) * 100)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=daily_roi, mode='lines+markers', name='ROI (%)'))
            fig.update_layout(
                title="ROI Diario",
                xaxis_title="Fecha",
                yaxis_title="ROI (%)",
                template="plotly_dark"
            )
            fig.write_html(f"roi_plot_{now.strftime('%Y-%m-%d')}.html")
            logger.info(f"[CierreTrading] Gráfico interactivo de ROI generado: roi_plot_{now.strftime('%Y-%m-%d')}.html")
        except Exception as e:
            logger.error(f"[CierreTrading] Error al generar gráfico de ROI: {e}")

    async def close_trade(self, bloque, trade):
        try:
            current_price = bloque.memoria_colectiva[-1]["precio"] if bloque.memoria_colectiva else 50000
            profit = trade["cantidad"] * (current_price - trade["price"])
            bloque.capital += trade["cantidad"] + profit
            self.trades_history.append({
                "profit": profit,
                "timestamp": datetime.utcnow().isoformat(),
                "is_win": profit > 0
            })
            bloque.memoria_colectiva.append({
                "decision": "cerrar",
                "profit": profit,
                "timestamp": datetime.utcnow().isoformat()
            })
            logger.info(f"[CierreTrading] Operación cerrada: Profit=${profit}, Capital=${bloque.capital}")
        except Exception as e:
            logger.error(f"[CierreTrading] Error cerrando operación: {e}")

    async def micro_cycle(self):
        try:
            now = datetime.now()
            daily_profit = 0
            for bloque in self.controller.nucleus.bloques:
                if bloque.memoria_colectiva:
                    current_price = bloque.memoria_colectiva[-1]["precio"]
                    for trade in bloque.memoria_colectiva:
                        if trade["decision"] in ["comprar", "vender"]:
                            profit = trade["cantidad"] * (current_price - trade["price"])
                            profit_pct = profit / (trade["price"] * trade["cantidad"])
                            if abs(profit_pct) > self.micro_cycle_profit_threshold:
                                daily_profit += profit
                                await self.close_trade(bloque, trade)
            logger.info(f"[CierreTrading] Micro-ciclo a las {now.hour}:00: Ganancia/Pérdida: ${daily_profit}")
        except Exception as e:
            logger.error(f"[CierreTrading] Error en micro-ciclo: {e}")

    async def handle_market_crash(self):
        try:
            macro_data = await self.redis.get("market:macro")
            if not macro_data:
                return
            macro_data = json.loads(macro_data)
            btc_change = self.controller.nucleus.historical_data.get("BTC/USDT", {}).get("price_change", 0)
            sp500_change = macro_data.get("SP500", 0.0)

            # Calcular proporción de entidades en estrés
            stress_count = sum(1 for b in self.controller.nucleus.bloques for e in b.entidades if e.memoria_simbolica and e.memoria_simbolica[-1]["emocion"] == "estrés")
            total_entities = sum(len(b.entidades) for b in self.controller.nucleus.bloques)
            stress_ratio = stress_count / total_entities if total_entities > 0 else 0.0

            if (btc_change < self.crash_threshold or sp500_change < self.crash_threshold or stress_ratio > self.stress_threshold):
                logger.warning("[CierreTrading] Caída del mercado detectada: pausando operaciones")
                self.is_paused = True
                self.recovery_capital_percentage = 0.1
                self.crash_count += 1
                self.crash_duration += 1

                # Extender pausa si la caída persiste
                pause_hours = 2 if self.crash_duration >= 6 else 1

                if self.crash_count > 2:
                    self.crash_threshold = max(self.crash_threshold * 0.75, -0.15)
                    self.crash_count = 0
                    logger.info(f"[CierreTrading] Umbral de caídas ajustado a {self.crash_threshold*100:.2f}% debido a caídas frecuentes")

                alert = {
                    "tipo": "evento_critico",
                    "plugin_id": "crypto_trading",
                    "evento": "caida_mercado",
                    "detalle": f"Caída detectada: BTC {btc_change*100:.2f}%, SP500 {sp500_change*100:.2f}%, Estrés {stress_ratio*100:.2f}%",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await self.redis.xadd("critical_events", {"data": json.dumps(alert)})
                await self.controller.publicar_evento(
                    canal="alertas",
                    datos=alert,
                    destino="trading"
                )

                for bloque in self.controller.nucleus.bloques:
                    for trade in bloque.memoria_colectiva:
                        if trade["decision"] in ["comprar", "vender"]:
                            await self.close_trade(bloque, trade)

                # Mutación colectiva para estabilizar
                if stress_ratio > self.stress_threshold:
                    for bloque in self.controller.nucleus.bloques:
                        for entidad in bloque.entidades:
                            entidad.mutar(nueva_etiqueta="tierra", nueva_emocion="neutral")

                for i in range(pause_hours * 6):
                    await asyncio.sleep(600)
                    self.recovery_capital_percentage = min(1.0, self.recovery_capital_percentage + 0.15)
                    logger.info(f"[CierreTrading] Recuperación gradual: {self.recovery_capital_percentage*100:.2f}% del capital disponible")
                self.is_paused = False
                self.crash_duration = 0
        except Exception as e:
            logger.error(f"[CierreTrading] Error al manejar caída del mercado: {e}")

    async def execute_daily_close(self) -> None:
        try:
            now = datetime.now()
            metrics = await self.calculate_advanced_metrics()
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "daily_settlement"},
                destino="trading"
            )
            await self.save_metrics_to_db(metrics)
            await self.generate_roi_plot(now)
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "cierre_diario", "mensaje": "Cierre diario completado", "metrics": metrics},
                destino="trading"
            )
            logger.info("[CierreTrading] Cierre diario ejecutado: %s", metrics)
        except Exception as e:
            logger.error(f"[CierreTrading] Error ejecutando cierre diario: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_clock":
                now = datetime.now().time()
                if now.hour == self.cierre_hora.hour and now.minute == self.cierre_hora.minute:
                    await self.execute_daily_close()
                elif event.datos.get("texto") == "micro_cycle":
                    await self.micro_cycle()
        except Exception as e:
            logger.error(f"[CierreTrading] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        self.scheduler.shutdown()
        if self.db_pool:
            await self.db_pool.close()
            logger.info("[CierreTrading] Desconectado de PostgreSQL")
        logger.info("[CierreTrading] Apagado")
        await super().shutdown()
