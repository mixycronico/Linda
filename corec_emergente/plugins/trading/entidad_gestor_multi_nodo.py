#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_coordinacion_multi_nodo.py
Coordina tareas entre nodos distribuidos usando el enjambre de CoreC.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadCoordinacionMultiNodo(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_multi_nodo", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "nodo_count": 5,
            "auto_register_channels": True
        }
        super().__init__(id="multi_nodo_coordinador", config=config)
        self.nodo_count = config["nodo_count"]
        self.nodo_assignments = {}
        logger.info("[MultiNodoCoordinador] Inicializado")

    async def asignar_tareas(self, tasks):
        try:
            # Asignar tareas a bloques simbióticos del enjambre
            bloques = self.controller.nucleus.bloques
            for i, task in enumerate(tasks):
                bloque_id = i % len(bloques)
                self.nodo_assignments.setdefault(bloque_id, []).append(task)
                # Publicar tarea al bloque correspondiente
                await self.controller.publicar_evento(
                    canal="trading_strategy",
                    datos={"accion": "procesar_tarea", "tarea": task, "bloque_id": bloques[bloque_id].id},
                    destino="trading"
                )
            logger.info("[MultiNodoCoordinador] Tareas asignadas a %d bloques", len(bloques))
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "tareas_asignadas", "nodo_count": len(bloques), "tareas": len(tasks)},
                destino="trading"
            )
        except Exception as e:
            logger.error(f"[MultiNodoCoordinador] Error asignando tareas: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_multi_nodo" and event.datos.get("texto") == "asignar tareas":
                await self.asignar_tareas(event.datos.get("tasks", []))
        except Exception as e:
            logger.error(f"[MultiNodoCoordinador] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[MultiNodoCoordinador] Apagado")
        await super().shutdown()
