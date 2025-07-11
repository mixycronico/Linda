#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_gestor_capital.py
Gestiona el pool de capital compartido con distribución entre exchanges y ajuste dinámico.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime
import json
import os
import aioredis
import asyncpg
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadGestorCapitalPool(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_capital", "trading_comandos", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "max_capital_active_pct": 0.7,
            "max_users": 500,
            "min_capital_per_user": 10.0,
            "capital_pool_table": "capital_pool",
            "redis": {
                "enabled": True,
                "host": "localhost",
                "port": 6379,
                "db": 0
            },
            "postgres": {
                "enabled": False,
                "host": "localhost",
                "port": 5432,
                "database": "trading_db",
                "user": "trading_user",
                "password": "trading_pass"
            },
            "auto_register_channels": True,
            "estado_file": "estado_gestor_capital.json",
            "strategy_weights": {"momentum": 0.5, "scalping": 0.5}
        }
        super().__init__(id="gestor_capital_pool", config=config)
        self.max_capital_active_pct = config["max_capital_active_pct"]
        self.max_users = config["max_users"]
        self.min_capital_per_user = config["min_capital_per_user"]
        self.capital_pool_table = config["capital_pool_table"]
        self.estado_file = config["estado_file"]
        self.redis_config = config["redis"]
        self.postgres_config = config["postgres"]
        self.redis = None
        self.db_pool = None
        self.users = self._load_local_state()
        self.total_capital = sum(u["capital_inicial"] for u in self.users.values())
        self.active_capital = 0.0
        self.strategy_weights = config["strategy_weights"]
        self.strategy_performance = {"momentum": 0.0, "scalping": 0.0}
        self.base_capital = 100
        logger.info("[GestorCapitalPool] Inicializado")

    async def init(self) -> None:
        await super().init()
        if self.redis_config.get("enabled"):
            try:
                self.redis = await aioredis.create_redis_pool(
                    f"redis://{self.redis_config['host']}:{self.redis_config['port']}/{self.redis_config['db']}"
                )
                logger.info("[GestorCapitalPool] Conectado a Redis")
            except Exception as e:
                logger.error(f"[GestorCapitalPool] Error conectando a Redis: {e}")
        if self.postgres_config.get("enabled"):
            try:
                self.db_pool = await asyncpg.create_pool(
                    host=self.postgres_config["host"],
                    port=self.postgres_config["port"],
                    database=self.postgres_config["database"],
                    user=self.postgres_config["user"],
                    password=self.postgres_config["password"]
                )
                logger.info("[GestorCapitalPool] Conectado a PostgreSQL")
            except Exception as e:
                logger.error(f"[GestorCapitalPool] Error conectando a PostgreSQL: {e}")

    def _load_local_state(self) -> Dict:
        if self.redis_config.get("enabled") and self.redis:
            try:
                data = self.redis.get("gestor_capital_state")
                if data:
                    return json.loads(data.decode())
            except Exception as e:
                logger.error(f"[GestorCapitalPool] Error cargando estado desde Redis: {e}")
        if os.path.exists(self.estado_file):
            try:
                with open(self.estado_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[GestorCapitalPool] Error cargando estado local: {e}")
        return {}

    async def _save_local_state(self) -> None:
        try:
            with open(self.estado_file, "w") as f:
                json.dump(self.users, f, indent=2)
            if self.redis_config.get("enabled") and self.redis:
                await self.redis.set("gestor_capital_state", json.dumps(self.users))
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error guardando estado: {e}")

    async def add_user(self, usuario_id: str, capital_inicial: float) -> bool:
        try:
            if len(self.users) >= self.max_users:
                logger.error(f"[GestorCapitalPool] Máximo de usuarios alcanzado ({self.max_users})")
                return False
            if capital_inicial < self.min_capital_per_user:
                logger.error(f"[GestorCapitalPool] Capital inicial ({capital_inicial}) menor al mínimo ({self.min_capital_per_user})")
                return False
            if usuario_id in self.users:
                logger.warning(f"[GestorCapitalPool] Usuario {usuario_id} ya existe")
                return False

            self.users[usuario_id] = {
                "usuario_id": usuario_id,
                "capital_inicial": capital_inicial,
                "capital_disponible": capital_inicial,
                "ganancia_shadow": 0.0,
                "porcentaje_participacion": 0.0,
                "historial_operaciones": []
            }
            self.total_capital += capital_inicial
            await self.update_participations()
            await self.save_user_to_db(usuario_id)
            await self._save_local_state()
            logger.info(f"[GestorCapitalPool] Usuario {usuario_id} añadido con capital {capital_inicial}")
            return True
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error añadiendo usuario {usuario_id}: {e}")
            return False

    async def remove_user(self, usuario_id: str) -> bool:
        try:
            if usuario_id not in self.users:
                logger.error(f"[GestorCapitalPool] Usuario {usuario_id} no encontrado")
                return False
            user = self.users[usuario_id]
            if user["historial_operaciones"]:
                logger.warning(f"[GestorCapitalPool] Usuario {usuario_id} tiene operaciones activas, liquidación en cierre diario")
                return False
            self.total_capital -= user["capital_inicial"]
            del self.users[usuario_id]
            await self.update_participations()
            await self.save_user_to_db(usuario_id, delete=True)
            await self._save_local_state()
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "usuario_eliminado_pool", "usuario_id": usuario_id},
                destino="trading"
            )
            logger.info(f"[GestorCapitalPool] Usuario {usuario_id} eliminado")
            return True
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error eliminando usuario {usuario_id}: {e}")
            return False

    async def deposit_funds(self, usuario_id: str, amount: float) -> bool:
        try:
            if usuario_id not in self.users:
                logger.error(f"[GestorCapitalPool] Usuario {usuario_id} no encontrado")
                return False
            if amount <= 0:
                logger.error(f"[GestorCapitalPool] Cantidad inválida: {amount}")
                return False
            user = self.users[usuario_id]
            user["capital_inicial"] += amount
            user["capital_disponible"] += amount
            self.total_capital += amount
            await self.update_participations()
            await self.save_user_to_db(usuario_id)
            await self._save_local_state()
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "deposito_pool", "usuario_id": usuario_id, "amount": amount},
                destino="trading"
            )
            logger.info(f"[GestorCapitalPool] Depósito de {amount} para {usuario_id}")
            return True
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error depositando fondos para {usuario_id}: {e}")
            return False

    async def withdraw_funds(self, usuario_id: str, amount: float) -> bool:
        try:
            if usuario_id not in self.users:
                logger.error(f"[GestorCapitalPool] Usuario {usuario_id} no encontrado")
                return False
            user = self.users[usuario_id]
            if amount <= 0 or user["capital_disponible"] < amount:
                logger.error(f"[GestorCapitalPool] Capital insuficiente para {usuario_id}: {user['capital_disponible']}/{amount}")
                return False
            user["capital_inicial"] -= amount
            user["capital_disponible"] -= amount
            self.total_capital -= amount
            await self.update_participations()
            await self.save_user_to_db(usuario_id)
            await self._save_local_state()
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "retiro_pool", "usuario_id": usuario_id, "amount": amount},
                destino="trading"
            )
            logger.info(f"[GestorCapitalPool] Retiro de {amount} para {usuario_id}")
            return True
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error retirando fondos para {usuario_id}: {e}")
            return False

    async def update_participations(self) -> None:
        try:
            if not self.total_capital:
                for user in self.users.values():
                    user["porcentaje_participacion"] = 0.0
                return
            for user in self.users.values():
                user["porcentaje_participacion"] = user["capital_inicial"] / self.total_capital
            logger.debug("[GestorCapitalPool] Participaciones actualizadas")
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error actualizando participaciones: {e}")

    async def save_user_to_db(self, usuario_id: str, delete: bool = False) -> None:
        if not self.postgres_config.get("enabled") or not self.db_pool:
            return
        try:
            async with self.db_pool.acquire() as conn:
                if delete:
                    await conn.execute(
                        """
                        DELETE FROM capital_pool WHERE usuario_id = $1
                        """,
                        usuario_id
                    )
                else:
                    user = self.users.get(usuario_id, {})
                    await conn.execute(
                        """
                        INSERT INTO capital_pool (usuario_id, capital_inicial, capital_disponible, ganancia_shadow, porcentaje_participacion, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (usuario_id) DO UPDATE
                        SET capital_inicial = EXCLUDED.capital_inicial,
                            capital_disponible = EXCLUDED.capital_disponible,
                            ganancia_shadow = EXCLUDED.ganancia_shadow,
                            porcentaje_participacion = EXCLUDED.porcentaje_participacion,
                            timestamp = EXCLUDED.timestamp
                        """,
                        user.get("usuario_id"), user.get("capital_inicial"), user.get("capital_disponible"),
                        user.get("ganancia_shadow"), user.get("porcentaje_participacion"), datetime.utcnow()
                    )
            logger.debug(f"[GestorCapitalPool] Usuario {usuario_id} guardado en PostgreSQL")
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error guardando usuario {usuario_id} en PostgreSQL: {e}")

    async def distribute_capital(self, exchanges: List[str]) -> Dict[str, float]:
        try:
            capital_utilizable = self.total_capital * self.max_capital_active_pct
            num_ex = len(exchanges)
            if num_ex == 0:
                logger.warning("[GestorCapitalPool] No hay exchanges disponibles")
                return {}
            por_exchange = capital_utilizable / num_ex
            allocated = {ex: por_exchange for ex in exchanges}
            logger.info(f"[GestorCapitalPool] Capital distribuido: {allocated}")
            return allocated
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error distribuyendo capital: {e}")
            return {}

    async def update_strategy_performance(self, daily_profit: float):
        try:
            performance = daily_profit / self.base_capital
            self.strategy_performance["momentum"] += performance * self.strategy_weights["momentum"]
            self.strategy_performance["scalping"] += performance * self.strategy_weights["scalping"]
            total_score = sum(self.strategy_performance.values())
            if total_score > 0:
                self.strategy_weights["momentum"] = self.strategy_performance["momentum"] / total_score
                self.strategy_weights["scalping"] = self.strategy_performance["scalping"] / total_score
            else:
                self.strategy_weights = {"momentum": 0.5, "scalping": 0.5}
            logger.info(f"[GestorCapitalPool] Pesos de estrategias ajustados: Momentum {self.strategy_weights['momentum']*100:.2f}%, Scalping {self.strategy_weights['scalping']*100:.2f}%")
            await self.redis.set("strategy_weights", json.dumps(self.strategy_weights))
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error actualizando rendimiento de estrategias: {e}")

    async def adjust_base_capital(self):
        try:
            performance = self.total_capital / self.base_capital - 1
            if performance > 0.5:
                self.base_capital = min(self.base_capital * 1.2, 1000)
            elif performance < -0.2:
                self.base_capital = max(self.base_capital * 0.8, 50)
            logger.info(f"[GestorCapitalPool] Capital base ajustado: ${self.base_capital}")
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error ajustando capital base: {e}")

    async def allocate_trade(self, trade_amount: float, trade_id: str) -> Dict[str, float]:
        try:
            max_active = self.total_capital * self.max_capital_active_pct
            if self.active_capital + trade_amount > max_active:
                logger.warning(f"[GestorCapitalPool] Límite de capital activo alcanzado ({self.active_capital}/{max_active})")
                await self.controller.publicar_evento(
                    canal="alertas",
                    datos={"tipo": "capital_limite", "mensaje": "Límite de capital activo alcanzado"},
                    destino="trading"
                )
                return {}
            allocations = {}
            for usuario_id, user in self.users.items():
                allocation = trade_amount * user["porcentaje_participacion"]
                if user["capital_disponible"] >= allocation:
                    allocations[usuario_id] = allocation
                    user["capital_disponible"] -= allocation
                    user["historial_operaciones"].append({"trade_id": trade_id, "amount": allocation, "timestamp": datetime.utcnow().isoformat()})
                    await self.save_user_to_db(usuario_id)
                else:
                    logger.warning(f"[GestorCapitalPool] Capital insuficiente para {usuario_id}: {user['capital_disponible']}/{allocation}")
            self.active_capital += trade_amount
            await self._save_local_state()
            logger.info(f"[GestorCapitalPool] Operación {trade_id} asignada: {trade_amount}")
            return allocations
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error asignando operación {trade_id}: {e}")
            return {}

    async def settle_trade(self, trade_id: str, profit_loss: float) -> None:
        try:
            total_allocation = sum(t["amount"] for u in self.users.values() for t in u["historial_operaciones"] if t["trade_id"] == trade_id)
            if total_allocation == 0:
                logger.warning(f"[GestorCapitalPool] No se encontraron asignaciones para trade {trade_id}")
                return
            for usuario_id, user in self.users.items():
                for trade in user["historial_operaciones"]:
                    if trade["trade_id"] == trade_id:
                        user_allocation = trade["amount"]
                        user_share = user_allocation / total_allocation
                        user["ganancia_shadow"] += profit_loss * user_share
                        user["capital_disponible"] += user_allocation
                        user["historial_operaciones"].remove(trade)
                        await self.save_user_to_db(usuario_id)
            self.active_capital -= total_allocation
            self.historical_profits.append(profit_loss)
            await self._save_local_state()
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "trade_liquidado", "trade_id": trade_id, "profit_loss": profit_loss},
                destino="trading"
            )
            logger.info(f"[GestorCapitalPool] Operación {trade_id} liquidada: P/L {profit_loss}")
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error liquidando operación {trade_id}: {e}")

    async def apply_daily_settlement(self) -> None:
        try:
            for usuario_id, user in self.users.items():
                user["capital_inicial"] += user["ganancia_shadow"]
                user["capital_disponible"] += user["ganancia_shadow"]
                user["ganancia_shadow"] = 0.0
                user["historial_operaciones"] = []
                await self.save_user_to_db(usuario_id)
            await self.update_participations()
            await self._save_local_state()
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "cierre_diario", "mensaje": "Cierre diario completado"},
                destino="trading"
            )
            logger.info("[GestorCapitalPool] Cierre diario aplicado")
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error aplicando cierre diario: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            datos = event.datos
            if event.canal == "trading_capital":
                if datos.get("accion") == "add_user":
                    await self.add_user(datos.get("usuario_id"), datos.get("capital_inicial"))
                elif datos.get("accion") == "remove_user":
                    await self.remove_user(datos.get("usuario_id"))
                elif datos.get("accion") == "deposit_funds":
                    await self.deposit_funds(datos.get("usuario_id"), datos.get("amount"))
                elif datos.get("accion") == "withdraw_funds":
                    await self.withdraw_funds(datos.get("usuario_id"), datos.get("amount"))
                elif datos.get("accion") == "allocate_trade":
                    await self.allocate_trade(datos.get("trade_amount"), datos.get("trade_id"))
                elif datos.get("accion") == "settle_trade":
                    await self.settle_trade(datos.get("trade_id"), datos.get("profit_loss"))
                elif datos.get("accion") == "daily_settlement":
                    await self.apply_daily_settlement()
        except Exception as e:
            logger.error(f"[GestorCapitalPool] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        await self._save_local_state()
        if self.redis:
            await self.redis.close()
            logger.info("[GestorCapitalPool] Desconectado de Redis")
        if self.db_pool:
            await self.db_pool.close()
            logger.info("[GestorCapitalPool] Desconectado de PostgreSQL")
        logger.info("[GestorCapitalPool] Apagado")
        await super().shutdown()
