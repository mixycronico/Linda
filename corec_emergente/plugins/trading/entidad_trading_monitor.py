#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_trading_monitor.py
Monitorea el estado del sistema de trading, incluyendo métricas del enjambre.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadTradingMonitor(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_monitor", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "auto_register_channels": True
        }
        super().__init__(id="trading_monitor", config=config)
        logger.info("[TradingMonitor] Inicializado")

    async def mostrar_estado(self):
        try:
            estado = {
                "bloques": len(self.controller.nucleus.bloques),
                "entidades": sum(len(b.entidades) for b in self.controller.nucleus.bloques),
                "capital_total": sum(b.capital + b.posicion * b.memoria_colectiva[-1]["precio"] for b in self.controller.nucleus.bloques if b.memoria_colectiva),
                "memoria_global": len(self.controller.nucleus.memoria_global),
                "relaciones_simbolicas": len(self.controller.nucleus.plugins["viviente"].grafo.relaciones),
                "entrelazamientos_promedio": sum(len(e.entrelazadas) for b in self.controller.nucleus.bloques for e in b.entidades) / sum(len(b.entidades) for b in self.controller.nucleus.bloques) if self.controller.nucleus.bloques else 0
            }
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "estado_trading", "mensaje": f"Sistema de trading operativo: {estado}"},
                destino="trading"
            )
            logger.info("[TradingMonitor] Estado del sistema publicado: %s", estado)
        except Exception as e:
            logger.error(f"[TradingMonitor] Error mostrando estado: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_monitor" and event.datos.get("texto") == "mostrar estado":
                await self.mostrar_estado()
        except Exception as e:
            logger.error(f"[TradingMonitor] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[TradingMonitor] Apagado")
        await super().shutdown()
