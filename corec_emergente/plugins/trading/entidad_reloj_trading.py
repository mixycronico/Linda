#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_reloj_trading.py
Controla el ciclo diario del sistema de trading con APScheduler.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadRelojTrading(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_comandos", "alertas", "trading_clock"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "vigilancia_inicio": "00:00",
            "vigilancia_fin": "03:00",
            "settlement_time": "23:59",
            "ciclo_intervalo": 60,
            "auto_register_channels": True
        }
        super().__init__(id="reloj_trading", config=config)
        self.vigilancia_inicio = time.fromisoformat(config["vigilancia_inicio"])
        self.vigilancia_fin = time.fromisoformat(config["vigilancia_fin"])
        self.settlement_time = config["settlement_time"]
        self.ciclo_intervalo = config["ciclo_intervalo"]
        self.modo = "activo"
        self.scheduler = AsyncIOScheduler()
        logger.info("[RelojTrading] Inicializado")

    async def check_trading_mode(self) -> None:
        try:
            now = datetime.utcnow().time()
            if self.vigilancia_inicio <= now < self.vigilancia_fin:
                if self.modo != "vigilancia":
                    self.modo = "vigilancia"
                    logger.info("[RelojTrading] Modo vigilancia activado")
                    await self.controller.publicar_evento(
                        canal="trading_comandos",
                        datos={"texto": "modo_vigilancia"},
                        destino="trading"
                    )
            else:
                if self.modo != "activo":
                    self.modo = "activo"
                    logger.info("[RelojTrading] Modo activo activado")
                    await self.controller.publicar_evento(
                        canal="trading_comandos",
                        datos={"texto": "modo_activo"},
                        destino="trading"
                    )
        except Exception as e:
            logger.error(f"[RelojTrading] Error verificando modo de trading: {e}")

    async def check_market_crash(self) -> None:
        try:
            await self.controller.publicar_evento(
                canal="trading_clock",
                datos={"texto": "check_crash"},
                destino="trading"
            )
        except Exception as e:
            logger.error(f"[RelojTrading] Error verificando caída del mercado: {e}")

    async def init(self) -> None:
        await super().init()
        self.scheduler.add_job(
            self.check_trading_mode,
            IntervalTrigger(seconds=self.ciclo_intervalo),
            id="check_trading_mode",
            replace_existing=True
        )
        self.scheduler.add_job(
            self.check_market_crash,
            IntervalTrigger(seconds=60),
            id="check_market_crash",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("[RelojTrading] Scheduler iniciado")

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_comandos" and event.datos.get("texto") == "check_clock":
                await self.check_trading_mode()
        except Exception as e:
            logger.error(f"[RelojTrading] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        self.scheduler.shutdown()
        logger.info("[RelojTrading] Apagado")
        await super().shutdown()
