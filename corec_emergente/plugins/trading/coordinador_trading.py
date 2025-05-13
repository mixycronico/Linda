#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coordinador_trading.py
Orquesta las entidades del plugin de trading en CoreC Emergente.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadCoordinadorTrading(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": [
                "trading_comandos", "trading_respuestas", "trading_alertas",
                "trading_backtest", "trading_monitor", "trading_multi_nodo",
                "trading_usuarios", "trading_capital", "trading_clock",
                "trading_macro", "alertas"
            ],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "auto_register_channels": True
        }
        super().__init__(id="coordinador_trading", config=config)
        logger.info("[CoordinadorTrading] Inicializado")

    async def evaluar_salud_simbolica(self):
        try:
            necesita_ajuste, nueva_etiqueta, nueva_emocion = await self.controller.nucleus.evaluar_salud_simbolica()
            if necesita_ajuste:
                await self.controller.publicar_evento(
                    canal="trading_strategy",
                    datos={"accion": "ajustar_salud", "nueva_etiqueta": nueva_etiqueta, "nueva_emocion": nueva_emocion},
                    destino="trading"
                )
                logger.info(f"[CoordinadorTrading] Ajuste de salud simbólica solicitado: {nueva_etiqueta}, {nueva_emocion}")
        except Exception as e:
            logger.error(f"[CoordinadorTrading] Error evaluando salud simbólica: {e}")

    async def manejar_evento(self, event: Event) -> None:
        try:
            datos = event.datos
            if event.canal == "trading_comandos":
                comando = datos.get("texto", "").lower().strip()
                if comando == "ejecutar estrategia":
                    await self.controller.publicar_evento(
                        canal="trading_strategy",
                        datos={"texto": "ejecutar predicciones"},
                        destino="trading"
                    )
                elif comando == "mostrar estado trading":
                    await self.controller.publicar_evento(
                        canal="trading_monitor",
                        datos={"texto": "mostrar estado"},
                        destino="trading"
                    )
                elif comando == "detener trading":
                    await self.controller.publicar_evento(
                        canal="alertas",
                        datos={"tipo": "trading_detener", "mensaje": "Sistema de trading detenido"},
                        destino="trading"
                    )
                elif comando.startswith("register_user"):
                    parts = comando.split()
                    if len(parts) >= 3:
                        usuario_id, capital = parts[1], float(parts[2])
                        await self.controller.publicar_evento(
                            canal="trading_usuarios",
                            datos={"accion": "register_user", "usuario_id": usuario_id, "capital_inicial": capital},
                            destino="trading"
                        )
                elif comando.startswith("deposit_funds"):
                    parts = comando.split()
                    if len(parts) >= 3:
                        usuario_id, amount = parts[1], float(parts[2])
                        await self.controller.publicar_evento(
                            canal="trading_usuarios",
                            datos={"accion": "deposit_funds", "usuario_id": usuario_id, "amount": amount},
                            destino="trading"
                        )
                elif comando.startswith("withdraw_funds"):
                    parts = comando.split()
                    if len(parts) >= 3:
                        usuario_id, amount = parts[1], float(parts[2])
                        await self.controller.publicar_evento(
                            canal="trading_usuarios",
                            datos={"accion": "withdraw_funds", "usuario_id": usuario_id, "amount": amount},
                            destino="trading"
                        )
                elif comando == "monitorear altcoins":
                    await self.controller.publicar_evento(
                        canal="trading_altcoin",
                        datos={"texto": "monitorear altcoins"},
                        destino="trading"
                    )
                elif comando == "evaluar_salud_simbolica":
                    await self.evaluar_salud_simbolica()
        except Exception as e:
            logger.error(f"[CoordinadorTrading] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[CoordinadorTrading] Apagado")
        await super().shutdown()
