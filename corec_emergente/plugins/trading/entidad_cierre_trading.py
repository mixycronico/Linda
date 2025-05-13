#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_cierre_trading.py
Ejecuta el cierre diario a las 23:59 con métricas avanzadas y manejo de caídas.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime
import asyncpg
import numpy as np
import plotly.graph_objects as go
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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
            "settlement_time": "23:59",
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
            "crash_threshold": -0.2
        }
        super().__init__(id="cierre_trading", config=config)
        self.settlement_time = config["settlement_time"]
        self.metrics_table = config["metrics_table"]
        self.postgres_config = config["postgres"]
        self.crash_threshold = config["crash_threshold"]
        self.db_pool = None
        self.scheduler = AsyncIOScheduler()
        self.is_paused = False
        self.recovery_capital_percentage = 0.1
        self.crash_count = 0
        self.historical_profits = []
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
        h, m = map(int, self.settlement_time.split(":"))
        self.scheduler.add_job(
            self.execute_daily_close,
            CronTrigger(hour=h, minute=m),
            id="daily_close",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("[CierreTrading] Scheduler iniciado para cierre diario")

    async def calculate_advanced_metrics(self) -> Dict:
        metrics = {
            "total_capital": 0.0,
            "active_capital": 0.0,
            "users_count": 0,
            "trades_count": 0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_consecutive_losses": 0
        }
        try:
            metrics["total_capital"] = sum(b.capital + b.posicion * b.memoria_colectiva[-1]["precio"] for b in self.controller.nucleus.bloques if b.memoria_colectiva)
            metrics["active_capital"] = sum(u["capital_disponible"] for u in self.controller.gestor_capital.users.values())
            metrics["users_count"] = len(self.controller.gestor_capital.users)
            trades = self.historical_profits
            metrics["trades_count"] = len(trades)
            wins = sum(1 for t in trades if t > 0)
            metrics["win_rate"] = (wins / len(trades) * 100) if trades else 0.0
            returns = np.array(trades) / metrics["total_capital"] if trades else np.array([0.0])
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            metrics["sharpe_ratio"] = (mean_return / std_return * np.sqrt(365)) if std_return > 0 else 0.0
            cumulative = np.cumsum(trades)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative) / peak if peak.any() else np.array([0.0])
            metrics["max_drawdown"] = np.max(drawdown) if drawdown.any() else 0.0
            max_consecutive_losses = 0
            current_consecutive_losses = 0
            for t in trades:
                if t < 0:
                    current_consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
                else:
                    current_consecutive_losses = 0
            metrics["max_consecutive_losses"] = max_consecutive_losses
            return metrics
        except Exception as e:
            logger.error(f"[CierreTrading] Error calculando métricas avanzadas: {e}")
            return metrics

    async def generate_roi_plot(self, now: datetime) -> None:
        try:
            dates = [now.date()]
            daily_roi = [(sum(self.historical_profits) / self.capital) * 100]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=daily_roi, mode='lines+markers', name='ROI (%)'))
            fig.update_layout(
                title="ROI Diario",
                xaxis_title="Fecha",
                yaxis_title="ROI (%)",
                template="plotly_dark"
            )
            fig.write_html(f"roi_plot_{now.strftime('%Y-%m-%d')}.html")
            logger.info(f"[CierreTrading] Gráfico de ROI generado: roi_plot_{now.strftime('%Y-%m-%d')}.html")
        except Exception as e:
            logger.error(f"[CierreTrading] Error generando gráfico de ROI: {e}")

    async def save_metrics_to_db(self, metrics: Dict) -> None:
        if not self.postgres_config.get("enabled") or not self.db_pool:
            return
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO daily_metrics (total_capital, active_capital, users_count, trades_count, 
                                               win_rate, sharpe_ratio, max_drawdown, max_consecutive_losses, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    metrics["total_capital"], metrics["active_capital"], metrics["users_count"],
                    metrics["trades_count"], metrics["win_rate"], metrics["sharpe_ratio"],
                    metrics["max_drawdown"], metrics["max_consecutive_losses"], datetime.utcnow()
                )
            logger.debug("[CierreTrading] Métricas guardadas en PostgreSQL")
        except Exception as e:
            logger.error(f"[CierreTrading] Error guardando métricas: {e}")

    async def execute_daily_close(self) -> None:
        try:
            now = datetime.utcnow()
            metrics = await self.calculate_advanced_metrics()
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "daily_settlement"},
                destino="trading"
            )
            await self.generate_roi_plot(now)
            await self.save_metrics_to_db(metrics)
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "cierre_diario", "mensaje": "Cierre diario completado", "metrics": metrics},
                destino="trading"
            )
            logger.info("[CierreTrading] Cierre diario ejecutado: %s", metrics)
        except Exception as e:
            logger.error(f"[CierreTrading] Error ejecutando cierre diario: {e}")

    async def handle_market_crash(self):
        try:
            macro_data = self.controller.nucleus.macro_data
            btc_change = self.controller.nucleus.market_data.get("BTC/USDT", {}).get("price_change", 0.0)
            sp500_change = macro_data.get("SP500", 0.0)
            bloque = self.controller.nucleus.bloques[0]
            emocion_dominante = Counter([e.memoria_simbolica[-1]["emocion"] for e in bloque.entidades if e.memoria_simbolica]).most_common(1)[0][0]
            if btc_change < self.crash_threshold or sp500_change < self.crash_threshold or emocion_dominante == "estrés":
                logger.warning("[CierreTrading] Caída del mercado detectada: pausando operaciones")
                self.is_paused = True
                self.recovery_capital_percentage = 0.1
                self.crash_count += 1
                if self.crash_count > 2:
                    self.crash_threshold = max(self.crash_threshold * 0.75, -0.15)
                    self.crash_count = 0
                    logger.info(f"[CierreTrading] Umbral de caídas ajustado a {self.crash_threshold*100:.2f}%")
                await self.controller.publicar_evento(
                    canal="alertas",
                    datos={"tipo": "market_crash", "mensaje": f"Caída detectada: BTC {btc_change*100:.2f}%, SP500 {sp500_change*100:.2f}%"},
                    destino="trading"
                )
                for i in range(6):
                    await asyncio.sleep(600)
                    self.recovery_capital_percentage = min(1.0, self.recovery_capital_percentage + 0.15)
                    logger.info(f"[CierreTrading] Recuperación gradual: {self.recovery_capital_percentage*100:.2f}%")
                self.is_paused = False
        except Exception as e:
            logger.error(f"[CierreTrading] Error manejando caída del mercado: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_clock" and event.datos.get("texto") == "check_crash":
                await self.handle_market_crash()
        except Exception as e:
            logger.error(f"[CierreTrading] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        self.scheduler.shutdown()
        if self.db_pool:
            await self.db_pool.close()
            logger.info("[CierreTrading] Desconectado de PostgreSQL")
        logger.info("[CierreTrading] Apagado")
        await super().shutdown()
