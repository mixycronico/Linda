#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_reloj_trading.py
Controla el ciclo diario del sistema de trading (vigilancia, activo, cierre).
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
from datetime import datetime, time

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
            "cierre_hora": "23:55",
            "ciclo_intervalo": 60,
            "auto_register_channels": True
        }
        super().__init__(id="reloj_trading", config=config)
        self.vigilancia_inicio = time.fromisoformat(config["vigilancia_inicio"])
        self.vigilancia_fin = time.fromisoformat(config["vigilancia_fin"])
        self.cierre_hora = time.fromisoformat(config["cierre_hora"])
        self.ciclo_intervalo = config["ciclo_intervalo"]
        self.modo = "activo"
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
            elif now >= self.cierre_hora:
                if self.modo != "cierre":
                    self.modo = "cierre"
                    logger.info("[RelojTrading] Modo cierre activado")
                    await self.controller.publicar_evento(
                        canal="trading_clock",
                        datos={"texto": "ejecutar_cierre"},
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

    async def run_clock(self) -> None:
        try:
            while not self._shutdown:
                await self.check_trading_mode()
                await asyncio.sleep(self.ciclo_intervalo)
        except Exception as e:
            logger.error(f"[RelojTrading] Error ejecutando reloj: {e}")

    async def init(self) -> None:
        await super().init()
        asyncio.create_task(self.run_clock())

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_comandos" and event.datos.get("texto") == "check_clock":
                await self.check_trading_mode()
        except Exception as e:
            logger.error(f"[RelojTrading] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[RelojTrading] Apagado")
        await super().shutdown()
