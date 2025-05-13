#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_exchange_configurator.py
Configura exchanges desde multi_exchange_config.yaml.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadExchangeConfigurator(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["config_exchange", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "plantilla_path": "multi_exchange_config.yaml",
            "auto_register_channels": True
        }
        super().__init__(id="exchange_configurator", config=config)
        self.plantilla_path = config["plantilla_path"]
        self.active_exchanges = {}
        logger.info("[ExchangeConfigurator] Inicializado")

    async def cargar_configuracion(self) -> None:
        try:
            with open(self.plantilla_path, "r") as f:
                config = yaml.safe_load(f)
            for exchange, modes in config.items():
                if exchange == "capital_pool":
                    continue
                for mode, settings in modes.items():
                    if settings.get("enabled"):
                        self.active_exchanges[f"{exchange}_{mode}"] = {
                            "exchange": exchange,
                            "modo": mode,
                            "config": settings
                        }
                        await self.controller.publicar_evento(
                            canal="trading_exchange",
                            datos={"tipo": "registro_exchange", "exchange": exchange, "modo": mode, "config": settings},
                            destino="trading"
                        )
            logger.info("[ExchangeConfigurator] Configuración cargada para %s exchanges", len(self.active_exchanges))
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "config_cargada", "exchanges": list(self.active_exchanges.keys())},
                destino="trading"
            )
        except Exception as e:
            logger.error(f"[ExchangeConfigurator] Error cargando configuración: {e}")
            await self.controller.publicar_evento(
                canal="alertas",
                datos={"tipo": "error_config", "mensaje": f"Error cargando configuración: {e}"},
                destino="trading"
            )

    async def manejar_evento(self, event: Event) -> None:
        try:
            datos = event.datos
            if event.canal == "config_exchange":
                if datos.get("accion") == "cargar_config":
                    await self.cargar_configuracion()
                elif datos.get("accion") == "reinicio_suave":
                    exchange = datos.get("exchange")
                    modo = datos.get("modo")
                    if f"{exchange}_{modo}" in self.active_exchanges:
                        await self.controller.publicar_evento(
                            canal="trading_exchange",
                            datos={"tipo": "registro_exchange", "exchange": exchange, "modo": modo, "config": self.active_exchanges[f"{exchange}_{modo}"]["config"]},
                            destino="trading"
                        )
                        logger.info(f"[ExchangeConfigurator] Reinicio suave para {exchange} ({modo})")
                        await self.controller.publicar_evento(
                            canal="alertas",
                            datos={"tipo": "reinicio_suave", "exchange": exchange, "modo": modo},
                            destino="trading"
                        )
        except Exception as e:
            logger.error(f"[ExchangeConfigurator] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[ExchangeConfigurator] Apagado")
        await super().shutdown()
