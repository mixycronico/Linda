import asyncio
import logging
import random
import math
from collections import Counter
import json
import aioredis
from datetime import datetime
from entities.nano import NanoEntidad
from blocks.symbiotic import BloqueSimbiotico
from channels import Channel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SistemaTradingTradicional:
    def __init__(self, capital_inicial=10000):
        self.capital = capital_inicial
        self.posicion = 0
        self.ganancia_neta = 0

    def procesar(self, carga):
        precio = carga["precio"]
        rsi = carga["rsi"]
        sma_signal = carga["sma_signal"]
        
        if rsi < 30 and sma_signal == 1 and self.capital > 0:
            cantidad = (self.capital * 0.1) / precio
            self.posicion += cantidad
            self.capital -= cantidad * precio
            logger.info(f"Tradicional: Compra {cantidad:.4f} BTC/ETH a {precio:.2f}")
        elif rsi > 70 and sma_signal == -1 and self.posicion > 0:
            self.capital += self.posicion * precio
            logger.info(f"Tradicional: Venta {self.posicion:.4f} BTC/ETH a {precio:.2f}")
            self.posicion = 0
        
        return (self.capital + self.posicion * precio - 10000) / 10000

class Nucleus:
    def __init__(self, config=None):
        self.config = config or {
            "redis": {"host": "localhost", "port": 6379, "db": 0},
            "memoria_max_global": 200,
            "log_level": "INFO"
        }
        self.canal = Channel(self.config["redis"])
        self.entidades = []
        self.bloques = []
        self.plugins = {}
        self.precios = []
        self.rsi = []
        self.sma = []
        self.dxy = []
        self.memoria_global = []
        self.memoria_max_global = self.config["memoria_max_global"]
        self.ciclo_actual = 0
        logger.setLevel(self.config["log_level"])
        logger.info("[Nucleus] Inicializado")

    async def registrar_entidad(self, entidad):
        self.entidades.append(entidad)
        logger.debug(f"[Nucleus] Entidad {entidad.id} registrada")

    async def registrar_bloque(self, bloque):
        self.bloques.append(bloque)
        logger.debug(f"[Nucleus] Bloque {bloque.id} registrado")

    async def registrar_plugin(self, nombre, plugin):
        self.plugins[nombre] = plugin
        await plugin.inicializar()
        logger.debug(f"[Nucleus] Plugin {nombre} registrado")

    def generar_datos_mercado(self, horas=720):
        precio_inicial = 50000
        precios = [precio_inicial]
        dxy = [100]
        for _ in range(horas - 1):
            cambio = random.gauss(0, 0.01) + 0.0005 * math.sin(_ / 24)
            precios.append(precios[-1] * (1 + cambio))
            dxy_cambio = random.gauss(0, 0.005) - 0.0002 * math.sin(_ / 24)
            dxy.append(dxy[-1] * (1 + dxy_cambio))
        
        rsi = []
        for i in range(horas):
            if i < 14:
                rsi.append(50)
            else:
                ganancias = [max(precios[j] - precios[j-1], 0) for j in range(i-13, i+1)]
                perdidas = [max(precios[j-1] - precios[j], 0) for j in range(i-13, i+1)]
                avg_ganancia = sum(ganancias) / 14
                avg_perdida = sum(perdidas) / 14
                rs = avg_ganancia / avg_perdida if avg_perdida > 0 else 100
                rsi.append(100 - 100 / (1 + rs))
        
        sma = []
        for i in range(horas):
            if i < 50:
                sma.append(precios[i])
            else:
                sma.append(sum(precios[i-49:i+1]) / 50)
        
        self.precios = precios
        self.rsi = rsi
        self.sma = sma
        self.dxy = dxy
        logger.info("[Nucleus] Datos de mercado generados para %d horas", horas)

    async def analizar_memoria_global(self):
        if not self.memoria_global:
            return False, None, None
        
        emociones = Counter([e["emocion"] for e in self.memoria_global])
        decisiones = Counter([e["decision"] for e in self.memoria_global])
        valores = [e["valor"] for e in self.memoria_global]
        valor_promedio = sum(valores) / len(valores) if valores else 0

        clusters = []
        if emociones["estrés"] > 0.4 * len(self.memoria_global):
            clusters.append(("estrés_dominante", decisiones["vender"], valor_promedio))
        if emociones["alegría"] > 0.4 * len(self.memoria_global):
            clusters.append(("alegría_dominante", decisiones["comprar"], valor_promedio))
        if emociones["curiosidad"] > 0.4 * len(self.memoria_global):
            clusters.append(("curiosidad_dominante", decisiones["mantener"], valor_promedio))

        necesita_mutacion = False
        nueva_etiqueta = None
        nueva_emocion = None

        for cluster, count, valor in clusters:
            if cluster == "estrés_dominante" and count > 0.5 * len(self.memoria_global):
                necesita_mutacion = True
                nueva_etiqueta = "tierra"
                nueva_emocion = "neutral"
            elif cluster == "alegría_dominante" and count > 0.4 * len(self.memoria_global) and valor < 0.3:
                necesita_mutacion = True
                nueva_etiqueta = "fuego"
                nueva_emocion = "curiosidad"
            elif cluster == "curiosidad_dominante" and count > 0.6 * len(self.memoria_global):
                necesita_mutacion = True
                nueva_etiqueta = "viento"
                nueva_emocion = "curiosidad"

        return necesita_mutacion, nueva_etiqueta, nueva_emocion

    async def evaluar_salud_simbolica(self):
        etiquetas = [e.etiqueta for b in self.bloques for e in b.entidades]
        emociones = [e.estado_emocional for b in self.bloques for e in b.entidades]
        etiqueta_counts = Counter(etiquetas)
        emocion_counts = Counter(emociones)
        
        entropia_etiquetas = -sum((count / len(etiquetas)) * math.log2(count / len(etiquetas)) for count in etiqueta_counts.values() if count > 0)
        varianza_emocional = sum((count / len(emociones) - 1/len(emocion_counts))**2 for count in emocion_counts.values())
        
        necesita_ajuste = entropia_etiquetas < 1.0 or varianza_emocional > 0.5
        if necesita_ajuste:
            nueva_etiqueta = random.choice(list(set(["fuego", "agua", "viento", "tierra"]) - set(etiqueta_counts.keys())))
            nueva_emocion = "curiosidad" if varianza_emocional > 0.5 else "neutral"
            logger.info(f"[Nucleus] Ajuste de salud simbólica necesario: entropía={entropia_etiquetas:.2f}, varianza={varianza_emocional:.2f}")
            return True, nueva_etiqueta, nueva_emocion
        return False, None, None

    async def simular(self, ciclos=720):
        self.generar_datos_mercado(ciclos)
        capital_inicial = sum(b.capital for b in self.bloques) / len(self.bloques)
        drawdown_max = 0
        sistema_tradicional = SistemaTradingTradicional(capital_inicial)
        retornos_tradicional = []
        mutaciones = 0
        relaciones_simbolicas = []
        entrelazamientos = []
        ajustes_salud = 0
        
        for ciclo in range(ciclos):
            self.ciclo_actual = ciclo
            logger.info(f"\n--- Ciclo {ciclo + 1} (Hora {ciclo}) ---")
            precio = self.precios[ciclo]
            sma_signal = 1 if precio > self.sma[ciclo] else -1
            volatilidad = 0.02 + 0.03 * random.random()
            dxy = self.dxy[ciclo]
            carga = {
                "precio": precio,
                "rsi": self.rsi[ciclo],
                "sma_signal": sma_signal,
                "volatilidad": volatilidad,
                "dxy": dxy
            }
            capital_total = 0
            for bloque in self.bloques:
                fitness = await bloque.procesar(carga)
                capital_actual = bloque.capital + bloque.posicion * precio
                capital_total += capital_actual
                drawdown = (capital_inicial - capital_actual) / capital_inicial
                drawdown_max = max(drawdown_max, drawdown)
                logger.info(f"Bloque {bloque.id} - Fitness: {fitness:.2%}, Capital: {capital_actual:.2f}, Drawdown: {drawdown:.2%}")
                for entidad in bloque.entidades:
                    logger.debug(f"  Entidad {entidad.id}: Etiqueta={entidad.etiqueta_colapsada}, Emoción={entidad.estado_emocional}, Decisión={entidad.memoria_simbolica[-1]['decision']}")
                if await bloque.reparar(fitness_threshold=0.01):
                    logger.info(f"Bloque {bloque.id} reparado mediante mutación")
                    mutaciones += 1
            
            necesita_mutacion, nueva_etiqueta, nueva_emocion = await self.analizar_memoria_global()
            if necesita_mutacion:
                for bloque in self.bloques:
                    for entidad in bloque.entidades:
                        entidad.mutar(nueva_etiqueta, nueva_emocion)
                logger.info(f"Enjambre: Mutación global a {nueva_etiqueta} con emoción {nueva_emocion}")
                mutaciones += 1

            if ciclo % 50 == 0:
                necesita_ajuste, nueva_etiqueta, nueva_emocion = await self.evaluar_salud_simbolica()
                if necesita_ajuste:
                    for bloque in self.bloques:
                        for entidad in random.sample(bloque.entidades, len(bloque.entidades) // 2):
                            entidad.mutar(nueva_etiqueta, nueva_emocion)
                    logger.info(f"Enjambre: Ajuste de salud simbólica a {nueva_etiqueta} con emoción {nueva_emocion}")
                    ajustes_salud += 1

            fitness_tradicional = sistema_tradicional.procesar(carga)
            capital_tradicional = sistema_tradicional.capital + sistema_tradicional.posicion * precio
            retornos_tradicional.append(fitness_tradicional)
            logger.info(f"Sistema Tradicional - Fitness: {fitness_tradicional:.2%}, Capital: {capital_tradicional:.2f}")
            
            relaciones_simbolicas.append(len(self.plugins["viviente"].grafo.relaciones))
            entrelazamientos.append(sum(len(e.entrelazadas) for e in self.entidades) / len(self.entidades) if self.entidades else 0)

        capital_final = sum(b.capital + b.posicion * precio for b in self.bloques) / len(self.bloques)
        roi = (capital_final - capital_inicial) / capital_inicial
        retornos = [(sum(b.capital + b.posicion * self.precios[i] for b in self.bloques) / len(self.bloques) - capital_inicial) / capital_inicial for i in range(ciclos)]
        sharpe = (sum(retornos) / len(retornos)) / (max(0.0001, sum((r - sum(retornos)/len(retornos))**2 for r in retornos)**0.5 / len(retornos))) if retornos else 0
        
        capital_final_tradicional = sistema_tradicional.capital + sistema_tradicional.posicion * precio
        roi_tradicional = (capital_final_tradicional - capital_inicial) / capital_inicial
        sharpe_tradicional = (sum(retornos_tradicional) / len(retornos_tradicional)) / (max(0.0001, sum((r - sum(retornos_tradicional)/len(retornos_tradicional))**2 for r in retornos_tradicional)**0.5 / len(retornos_tradicional))) if retornos_tradicional else 0
        
        logger.info(f"\n--- Resultados Finales ---")
        logger.info(f"CoreC Emergente (Enjambre):")
        logger.info(f"  ROI: {roi:.2%}")
        logger.info(f"  Sharpe Ratio: {sharpe:.2f}")
        logger.info(f"  Drawdown Máximo: {drawdown_max:.2%}")
        logger.info(f"  Capital Final Promedio: {capital_final:.2f} USDT")
        logger.info(f"  Mutaciones Simbólicas: {mutaciones}")
        logger.info(f"  Ajustes de Salud Simbólica: {ajustes_salud}")
        logger.info(f"  Relaciones Simbólicas Creadas: {max(relaciones_simbolicas)}")
        logger.info(f"  Promedio de Entrelazamientos por Entidad: {sum(entrelazamientos)/len(entrelazamientos):.2f}")
        logger.info(f"Sistema Tradicional:")
        logger.info(f"  ROI: {roi_tradicional:.2%}")
        logger.info(f"  Sharpe Ratio: {sharpe_tradicional:.2f}")
        logger.info(f"  Capital Final: {capital_final_tradicional:.2f} USDT")

    async def shutdown(self):
        for plugin in self.plugins.values():
            await plugin.shutdown()
        await self.canal.shutdown()
        logger.info("[Nucleus] Apagado")
