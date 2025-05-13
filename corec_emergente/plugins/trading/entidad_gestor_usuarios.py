#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_gestor_usuarios.py
Gestiona el ciclo de vida de usuarios con respaldo en Redis y PostgreSQL opcional.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime
import json
import os
import aioredis

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadGestorUsuarios(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_usuarios", "trading_capital", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "max_users": 500,
            "min_capital_per_user": 10.0,
            "users_table": "users",
            "redis": {
                "enabled": True,
                "host": "localhost",
                "port": 6379,
                "db": 0
            },
            "auto_register_channels": True,
            "estado_file": "estado_gestor_usuarios.json"
        }
        super().__init__(id="gestor_usuarios", config=config)
        self.max_users = config["max_users"]
        self.min_capital_per_user = config["min_capital_per_user"]
        self.users_table = config["users_table"]
        self.estado_file = config["estado_file"]
        self.redis_config = config["redis"]
        self.redis = None
        self.users = self._load_local_state()
        logger.info("[GestorUsuarios] Inicializado")

    async def init(self) -> None:
        await super().init()
        if self.redis_config.get("enabled"):
            try:
                self.redis = await aioredis.create_redis_pool(
                    f"redis://{self.redis_config['host']}:{self.redis_config['port']}/{self.redis_config['db']}"
                )
                logger.info("[GestorUsuarios] Conectado a Redis")
            except Exception as e:
                logger.error(f"[GestorUsuarios] Error conectando a Redis: {e}")

    def _load_local_state(self) -> Dict:
        try:
            if self.redis_config.get("enabled") and self.redis:
                data = self.redis.get("gestor_usuarios_state")
                if data:
                    return json.loads(data.decode())
            if os.path.exists(self.estado_file):
                with open(self.estado_file, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error cargando estado: {e}")
            return {}

    async def _save_local_state(self) -> None:
        try:
            with open(self.estado_file, "w") as f:
                json.dump(self.users, f, indent=2)
            if self.redis_config.get("enabled") and self.redis:
                await self.redis.set("gestor_usuarios_state", json.dumps(self.users))
            logger.debug("[GestorUsuarios] Estado guardado")
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error guardando estado: {e}")

    async def save_user_to_db(self, usuario_id: str, delete: bool = False) -> None:
        if self._use_postgres:
            try:
                async with self.db_pool.acquire() as conn:
                    if delete:
                        await conn.execute(
                            """
                            DELETE FROM users WHERE usuario_id = $1
                            """,
                            usuario_id
                        )
                    else:
                        user = self.users.get(usuario_id, {})
                        await conn.execute(
                            """
                            INSERT INTO users (usuario_id, capital_inicial, capital_disponible, status, timestamp)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (usuario_id) DO UPDATE
                            SET capital_inicial = EXCLUDED.capital_inicial,
                                capital_disponible = EXCLUDED.capital_disponible,
                                status = EXCLUDED.status,
                                timestamp = EXCLUDED.timestamp
                            """,
                            user.get("usuario_id"), user.get("capital_inicial"), user.get("capital_disponible"),
                            user.get("status", "active"), datetime.fromisoformat(user.get("timestamp", datetime.utcnow().isoformat()))
                        )
                logger.debug(f"[GestorUsuarios] Usuario {usuario_id} guardado en PostgreSQL")
            except Exception as e:
                logger.error(f"[GestorUsuarios] Error guardando usuario {usuario_id} en PostgreSQL: {e}")
        else:
            await self._save_local_state()

    async def register_user(self, usuario_id: str, capital_inicial: float) -> bool:
        try:
            if len(self.users) >= self.max_users:
                logger.error(f"[GestorUsuarios] Máximo de usuarios alcanzado ({self.max_users})")
                return False
            if capital_inicial < self.min_capital_per_user:
                logger.error(f"[GestorUsuarios] Capital inicial ({capital_inicial}) menor al mínimo ({self.min_capital_per_user})")
                return False
            if usuario_id in self.users:
                logger.warning(f"[GestorUsuarios] Usuario {usuario_id} ya existe")
                return False

            self.users[usuario_id] = {
                "usuario_id": usuario_id,
                "capital_inicial": capital_inicial,
                "capital_disponible": capital_inicial,
                "status": "active",
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.save_user_to_db(usuario_id)
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "add_user", "usuario_id": usuario_id, "capital_inicial": capital_inicial},
                destino="trading"
            )
            logger.info(f"[GestorUsuarios] Usuario {usuario_id} registrado con capital {capital_inicial}")
            return True
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error registrando usuario {usuario_id}: {e}")
            return False

    async def remove_user(self, usuario_id: str) -> bool:
        try:
            if usuario_id not in self.users:
                logger.error(f"[GestorUsuarios] Usuario {usuario_id} no encontrado")
                return False
            del self.users[usuario_id]
            await self.save_user_to_db(usuario_id, delete=True)
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "remove_user", "usuario_id": usuario_id},
                destino="trading"
            )
            logger.info(f"[GestorUsuarios] Usuario {usuario_id} eliminado")
            return True
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error eliminando usuario {usuario_id}: {e}")
            return False

    async def deposit_funds(self, usuario_id: str, amount: float) -> bool:
        try:
            if usuario_id not in self.users:
                logger.error(f"[GestorUsuarios] Usuario {usuario_id} no encontrado")
                return False
            if amount <= 0:
                logger.error(f"[GestorUsuarios] Cantidad inválida: {amount}")
                return False
            user = self.users[usuario_id]
            user["capital_inicial"] += amount
            user["capital_disponible"] += amount
            user["timestamp"] = datetime.utcnow().isoformat()
            await self.save_user_to_db(usuario_id)
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "deposit_funds", "usuario_id": usuario_id, "amount": amount},
                destino="trading"
            )
            logger.info(f"[GestorUsuarios] Depósito de {amount} para {usuario_id}")
            return True
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error depositando fondos para {usuario_id}: {e}")
            return False

    async def withdraw_funds(self, usuario_id: str, amount: float) -> bool:
        try:
            if usuario_id not in self.users:
                logger.error(f"[GestorUsuarios] Usuario {usuario_id} no encontrado")
                return False
            user = self.users[usuario_id]
            if amount <= 0 or user["capital_disponible"] < amount:
                logger.error(f"[GestorUsuarios] Fondos insuficientes o cantidad inválida para {usuario_id}: {user['capital_disponible']}/{amount}")
                return False
            user["capital_inicial"] -= amount
            user["capital_disponible"] -= amount
            user["timestamp"] = datetime.utcnow().isoformat()
            await self.save_user_to_db(usuario_id)
            await self.controller.publicar_evento(
                canal="trading_capital",
                datos={"accion": "withdraw_funds", "usuario_id": usuario_id, "amount": amount},
                destino="trading"
            )
            logger.info(f"[GestorUsuarios] Retiro de {amount} para {usuario_id}")
            return True
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error retirando fondos para {usuario_id}: {e}")
            return False

    async def manejar_evento(self, event: Event) -> None:
        try:
            datos = event.datos
            if event.canal == "trading_usuarios":
                if datos.get("accion") == "register_user":
                    await self.register_user(datos.get("usuario_id"), datos.get("capital_inicial"))
                elif datos.get("accion") == "remove_user":
                    await self.remove_user(datos.get("usuario_id"))
                elif datos.get("accion") == "deposit_funds":
                    await self.deposit_funds(datos.get("usuario_id"), datos.get("amount"))
                elif datos.get("accion") == "withdraw_funds":
                    await self.withdraw_funds(datos.get("usuario_id"), datos.get("amount"))
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        try:
            if not self._use_postgres:
                await self._save_local_state()
            if self.redis:
                await self.redis.close()
                logger.info("[GestorUsuarios] Desconectado de Redis")
            logger.info("[GestorUsuarios] Apagado")
            await super().shutdown()
        except Exception as e:
            logger.error(f"[GestorUsuarios] Error apagando: {e}")
