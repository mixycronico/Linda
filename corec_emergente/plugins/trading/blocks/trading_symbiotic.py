#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trading_symbiotic.py
Bloque simbiótico para trading, integrado con el enjambre de CoreC Emergente.
"""

from collections import Counter
import json
import random
import logging
from entities.nano import NanoEntidad

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradingSymbioticBlock:
    def __init__(self, id, entidades, canal, config):
        self.id = id
        self.entidades = entidades
        self.canal = canal
        self.capital = config.get("capital", 10000)
        self.posicion = 0
        self.ganancia_neta = 0
        self.memoria_colectiva = []
        self.memoria_max = config.get("memoria_max", 50)
        self.estres_consecutivo = 0
        self._inicializar_entrelazamiento()
        self.canal.subscribe("bloque_comunicacion", self.recibir_mensaje)
        logger.debug(f"[TradingSymbioticBlock] {self.id} inicializado")

    def _inicializar_entrelazamiento(self):
        for i, entidad in enumerate(self.entidades):
            for j, otra_entidad in enumerate(self.entidades):
                if i != j and entidad.etiqueta == otra_entidad.etiqueta:
                    entidad.entrelazadas.append(otra_entidad)
                    otra_entidad.entrelazadas.append(entidad)
            for bloque in [b for b in self.canal.subscribers["bloque_comunicacion"] if b != self]:
                for otra_entidad in bloque.entidades:
                    if entidad.etiqueta == otra_entidad.etiqueta and random.random() < 0.2:
                        entidad.entrelazadas.append(otra_entidad)
                        otra_entidad.entrelazadas.append(entidad)

    def _actualizar_entrelazamiento(self):
        try:
            grafo_resonancia = self.canal.nucleus.plugins["viviente"].grafo
            for entidad in self.entidades:
                entidad.entrelazadas = []
                for bloque in [b for b in self.canal.subscribers["bloque_comunicacion"] + [self]]:
                    for otra_entidad in bloque.entidades:
                        if entidad.id != otra_entidad.id and random.random() < 0.3:
                            fitness = bloque._calcular_fitness(bloque.memoria_colectiva[-5:], bloque.memoria_colectiva[-1]["precio"]) if bloque.memoria_colectiva else 0
                            if fitness > 0.02 or grafo_resonancia.calcular_impacto(entidad.etiqueta, otra_entidad.etiqueta) > 1.2:
                                entidad.entrelazadas.append(otra_entidad)
                                otra_entidad.entrelazadas.append(entidad)
            logger.debug(f"[TradingSymbioticBlock] {self.id} actualizó entrelazamientos")
        except Exception as e:
            logger.error(f"[TradingSymbioticBlock] Error actualizando entrelazamientos: {e}")

    async def procesar(self, carga: dict):
        try:
            precio = carga["precio"]
            resultados = []
            for entidad in self.entidades:
                resultado = await entidad.procesar(carga)
                resultados.append(resultado)
                self.memoria_colectiva.append(resultado)
            
            if len(self.memoria_colectiva) > self.memoria_max:
                self.memoria_colectiva = self.memoria_colectiva[-self.memoria_max:]
            
            estres_count = sum(1 for r in resultados if r["emocion"] == "estrés")
            if estres_count > len(self.entidades) / 2:
                self.estres_consecutivo += 1
            else:
                self.estres_consecutivo = 0
            if self.estres_consecutivo >= 5 and self.posicion > 0:
                self.capital += self.posicion * precio
                logger.info(f"[TradingSymbioticBlock] {self.id}: Stop-loss emocional - Venta {self.posicion:.4f} BTC/ETH a {precio:.2f}")
                self.posicion = 0
                self.estres_consecutivo = 0

            decisiones = [r["decision"] for r in resultados]
            if decisiones.count("comprar") > len(decisiones) / 2 and self.capital > 0 and carga["dxy"] < 100:
                cantidad = (self.capital * 0.1) / precio
                self.posicion += cantidad
                self.capital -= cantidad * precio
                logger.info(f"[TradingSymbioticBlock] {self.id}: Compra {cantidad:.4f} BTC/ETH a {precio:.2f}")
            elif decisiones.count("vender") > len(decisiones) / 2 and self.posicion > 0 and carga["dxy"] > 100:
                self.capital += self.posicion * precio
                logger.info(f"[TradingSymbioticBlock] {self.id}: Venta {self.posicion:.4f} BTC/ETH a {precio:.2f}")
                self.posicion = 0
            
            fitness = self._calcular_fitness(resultados, precio)
            mensaje = {
                "tipo": "bloque_mensaje",
                "id": self.id,
                "fitness": fitness,
                "peso": max(0, fitness * 10),
                "emocion_dominante": Counter([r["emocion"] for r in resultados]).most_common(1)[0][0],
                "etiqueta_dominante": Counter([r["etiqueta_colapsada"] for r in resultados]).most_common(1)[0][0],
                "timestamp": time.time()
            }
            await self.canal.publish("bloque_comunicacion", json.dumps(mensaje))
            await self.canal.publish("global_memoria", json.dumps(resultados[0]))
            
            if self.canal.nucleus.ciclo_actual % 50 == 0:
                self._actualizar_entrelazamiento()
            
            logger.debug(f"[TradingSymbioticBlock] {self.id} procesó carga, fitness: {fitness:.2%}")
            return fitness
        except Exception as e:
            logger.error(f"[TradingSymbioticBlock] Error procesando carga: {e}")
            return 0.0

    async def recibir_mensaje(self, mensaje):
        try:
            data = json.loads(mensaje)
            if data["id"] == self.id or data["tipo"] != "bloque_mensaje":
                return
            if data["peso"] > 0.5:
                if data["fitness"] > 0.05 and data["emocion_dominante"] == "alegría":
                    for entidad in self.entidades:
                        if random.random() < 0.4:
                            entidad.estado_emocional = "curiosidad"
                            entidad.mutar(nueva_etiqueta="fuego")
                elif data["fitness"] < -0.05 and data["emocion_dominante"] == "estrés":
                    for entidad in self.entidades:
                        if random.random() < 0.4:
                            entidad.estado_emocional = "neutral"
                            entidad.mutar(nueva_etiqueta="tierra")
            logger.debug(f"[TradingSymbioticBlock] {self.id} recibió mensaje de {data['id']}")
        except Exception as e:
            logger.error(f"[TradingSymbioticBlock] Error recibiendo mensaje: {e}")

    def _calcular_fitness(self, resultados, precio):
        try:
            estres_count = sum(1 for r in resultados if r["emocion"] == "estrés")
            fitness = (self.capital + self.posicion * precio - 10000) / 10000
            fitness *= (1 - 0.2 * estres_count / len(resultados))
            return fitness
        except Exception as e:
            logger.error(f"[TradingSymbioticBlock] Error calculando fitness: {e}")
            return 0.0

    async def analizar_memoria_colectiva(self):
        try:
            if not self.memoria_colectiva:
                return False, None, None
            
            decisiones = [e["decision"] for e in self.memoria_colectiva]
            emociones = [e["emocion"] for e in self.memoria_colectiva]
            valores = [e["valor"] for e in self.memoria_colectiva]
            decision_counts = Counter(decisiones)
            emocion_counts = Counter(emociones)
            valor_promedio = sum(valores) / len(valores) if valores else 0

            necesita_mutacion = False
            nueva_etiqueta = None
            nueva_emocion = None

            if emocion_counts["estrés"] > 0.5 * len(self.memoria_colectiva) and decision_counts["vender"] > 0.4 * len(self.memoria_colectiva):
                necesita_mutacion = True
                nueva_etiqueta = "tierra"
                nueva_emocion = "neutral"
            elif emocion_counts["alegría"] > 0.5 * len(self.memoria_colectiva) and decision_counts["comprar"] > 0.3 * len(self.memoria_colectiva) and valor_promedio < 0.3:
                necesita_mutacion = True
                nueva_etiqueta = "fuego"
                nueva_emocion = "curiosidad"
            elif emocion_counts["curiosidad"] > 0.5 * len(self.memoria_colectiva) and decision_counts["mantener"] > 0.6 * len(self.memoria_colectiva):
                necesita_mutacion = True
                nueva_etiqueta = "viento"
                nueva_emocion = "curiosidad"

            logger.debug(f"[TradingSymbioticBlock] {self.id} analizó memoria colectiva: necesita_mutacion={necesita_mutacion}")
            return necesita_mutacion, nueva_etiqueta, nueva_emocion
        except Exception as e:
            logger.error(f"[TradingSymbioticBlock] Error analizando memoria colectiva: {e}")
            return False, None, None

    async def reparar(self, fitness_threshold=0.01):
        try:
            fitness = await self.procesar(carga={"precio": 50000, "rsi": 50, "sma_signal": 0, "volatilidad": 0.02, "dxy": 100})
            if fitness < fitness_threshold:
                for entidad in self.entidades:
                    entidad.mutar()
                logger.info(f"[TradingSymbioticBlock] {self.id} reparado mediante mutación")
                return True
            return False
        except Exception as e:
            logger.error(f"[TradingSymbioticBlock] Error reparando bloque: {e}")
            return False
