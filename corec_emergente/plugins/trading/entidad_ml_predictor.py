#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_ml_predictor.py
Genera predicciones de precios usando el enjambre de CoreC en lugar de ML tradicional.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadMLPredictor(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_strategy", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "auto_register_channels": True
        }
        super().__init__(id="ml_predictor", config=config)
        logger.info("[MLPredictor] Inicializado")

    async def predict_price(self, symbol: str, exchange: str, modo: str) -> Dict:
        try:
            # Usar el enjambre para predicciones simbólicas
            for bloque in self.controller.nucleus.bloques:
                for entidad in bloque.entidades:
                    if entidad.memoria_simbolica:
                        evento = entidad.memoria_simbolica[-1]
                        base_price = 35000.0 if "BTC" in symbol else 2500.0 if "ETH" in symbol else 20.0
                        if evento["decision"] == "comprar":
                            return {
                                "symbol": symbol,
                                "predicted_price": base_price * 1.05,
                                "probability": 0.8
                            }
                        elif evento["decision"] == "vender":
                            return {
                                "symbol": symbol,
                                "predicted_price": base_price * 0.95,
                                "probability": 0.8
                            }
            return {
                "symbol": symbol,
                "predicted_price": base_price,
                "probability": 0.5
            }
        except Exception as e:
            logger.error(f"[MLPredictor] Error prediciendo precio para {symbol}: {e}")
            return {}

    async def manejar_evento(self, event: Event) -> None:
        try:
            if event.canal == "trading_strategy" and event.datos.get("texto") == "ejecutar predicciones":
                prediction = await self.predict_price("BTC/USDT", "binance", "spot")
                await self.controller.publicar_evento(
                    canal="trading_strategy",
                    datos=prediction,
                    destino="trading"
                )
                logger.info("[MLPredictor] Predicción publicada para BTC/USDT: %s", prediction)
        except Exception as e:
            logger.error(f"[MLPredictor] Error manejando evento: {e}")

    async def shutdown(self) -> None:
        logger.info("[MLPredictor] Apagado")
        await super().shutdown()
