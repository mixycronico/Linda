#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_cierre_trading.py
Ejecuta el cierre diario a las 23:55, aplicando resultados y consolidando métricas avanzadas.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime, time

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
            "cierre_hora": "23:55",
            "metrics_table": "daily_metrics",
            "auto_register_channels": True
        }
        super().__init__(id="cierre_trading", config=config)
        self.cierre_hora = time.fromisoformat(config["cierre_hora"])
        self.metrics_table = config["metrics_table"]
        logger.info("[CierreTrading] Inicializado")

    async def calculate_advanced_metrics(self) -> Dict:
        try:
            metrics = {
                "total_capital": sum(b.capital + b.posicion * b.memoria_colectiva[-1]["precio"] for b in self.controller.nucleus.bloques if b.memoria_colectiva),
                "active_capital": sum(u["capital_disponible"] for u in self.controller.gestor_capital.users.values()),
                "users_count": len(self.controller.gestor_capital.users),
                "trades_count": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_consecutive_losses": 0
            }
            if self._use_postgres:
                async with self.db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT outcome
                        FROM strategy_decisions
                        WHERE timestamp > NOW() - INTERVAL '1 day'
                        """
                    )
                    trades = [row["outcome"] for row in rows]
                    metrics["trades_count"] = len(trades)
                    wins = sum(1 for t in trades if t > 0)
                    metrics["win_rate"] = wins / len(trades) if trades else 0.0
                    gross_profit = sum(t for t in trades if t > 0)
                    gross_loss = sum(abs(t) for t in trades if t < 0)
                    metrics["profit_factor"] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
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
            return {
                "total_capital": 0.0,
                "active_capital": 0.0,
                "users_count": 0,
                "trades_count": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_consecutive_losses": 0
            }

    async def save_metrics_to_db(self, metrics: Dict) -> None:
        if self._use_postgres:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO daily_metrics (total_capital, active_capital, users_count, trades_count,
                                                   win_rate, profit_factor, max_consecutive_losses, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        metrics.get("total_capital", 0.0), metrics.get("active_capital", 0.0),
                        metrics.get("users_count", 0), metrics.get("trades_count", 0),
                        metrics.get("win_rate", 0.0), metrics.get("profit_factor", 0.0),
                        metrics.get("max_consecutive_losses", 0), datetime.utcnow()
                    )
                logger.debug("[CierreTrading] Métricas guardadas en PostgreSQL")
            except Exception as e:
                logger.error(f"[CierreTrading] Error guardando métricas: {e}")

    async def execute_daily_close(self) -> None:
        try:
            metrics = await self.calculate_advanced_metrics()
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "daily_settlement"},
                destino="trading"
            )
            await self.save_metrics_to_db(metrics)
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "cierre_diario", "mensaje": f"Cierre diario completado: {metrics}"},
                destino="trading"
            )
            logger.info("[CierreTrading] Cierre diario ejecutado: %s", metrics)
        except Exception as e:
            logger.error(f"[CierreTrading] Error ejecutando cierre diario: {e}")

    async def check_and_execute(self) -> None:
        try:
            now = datetime.utcnow().time()
            if now.hour == self.cierre_hora.hour and now.minute == self.cierre_hora.minute:
                await self.execute_daily_close()
        except Exception as e:
            logger.error(f"[CierreTrading] Error verificando cierre diario: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_clock":
                await self.check_and_execute()
        except Exception as e:
            logger.error(f"[CierreTrading] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[CierreTrading] Apagado")
        await super().shutdown()
