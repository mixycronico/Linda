import random
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NanoEntidad:
    def __init__(self, id, canal, valor_base=0.5):
        self.id = id
        self.canal = canal
        self.valor_base = valor_base
        self.memoria_simbolica = []
        self.memoria_max = 10
        self.estado_emocional = "neutral"
        self.emociones = {
            "alegría": 1.2, "estrés": 0.8, "curiosidad": 1.0, "neutral": 1.0
        }
        self.etiquetas_posibles = {
            "fuego": {"llama": 0.6, "ceniza": 0.3, "humo": 0.1},
            "agua": {"ola": 0.5, "vapor": 0.3, "hielo": 0.2},
            "viento": {"brisa": 0.7, "tormenta": 0.2, "calma": 0.1},
            "tierra": {"roca": 0.5, "arena": 0.3, "polvo": 0.2}
        }
        self.etiqueta = random.choice(list(self.etiquetas_posibles.keys()))
        self.estado_cuantico = self.etiquetas_posibles[self.etiqueta]
        self.entrelazadas = []
        logger.debug(f"[NanoEntidad] {self.id} inicializada")

    async def procesar(self, carga: dict):
        rsi = carga.get("rsi", 50)
        sma_signal = carga.get("sma_signal", 0)
        volatilidad = carga.get("volatilidad", 0.02)
        dxy = carga.get("dxy", 100)

        self.colapsar_estado(rsi, volatilidad, dxy)
        decision = self.generar_decision(carga)
        impacto = self.valor_base * self.emociones[self.estado_emocional]
        if self.estado_emocional == "estrés":
            impacto *= 0.5
        elif self.estado_emocional == "curiosidad":
            impacto *= 1.5

        self.actualizar_emocion(rsi, volatilidad, dxy)
        
        evento = {
            "tipo": "nano_emitido",
            "id": self.id,
            "etiqueta": self.etiqueta,
            "estado_cuantico": self.estado_cuantico,
            "etiqueta_colapsada": self.etiqueta_colapsada,
            "decision": decision,
            "valor": impacto,
            "emocion": self.estado_emocional,
            "timestamp": time.time()
        }
        self.memoria_simbolica.append(evento)
        if len(self.memoria_simbolica) > self.memoria_max:
            self.memoria_simbolica.pop(0)
        
        await self.canal.publish("nano_eventos", json.dumps(evento))
        logger.debug(f"[NanoEntidad] {self.id} procesó evento: {decision}")
        return evento

    def generar_decision(self, carga):
        rsi = carga.get("rsi", 50)
        sma_signal = carga.get("sma_signal", 0)
        dxy = carga.get("dxy", 100)
        if self.etiqueta in ["fuego", "viento"] and rsi < 30 and sma_signal == 1 and dxy < 100 and self.estado_emocional in ["alegría", "curiosidad"]:
            return "comprar"
        elif self.etiqueta in ["agua", "tierra"] and rsi > 70 and sma_signal == -1 and dxy > 100 or self.estado_emocional == "estrés":
            return "vender"
        return "mantener"

    def actualizar_emocion(self, rsi, volatilidad, dxy):
        emocion_entrelazada = self._obtener_emocion_entrelazada()
        if emocion_entrelazada and random.random() < 0.3:
            self.estado_emocional = emocion_entrelazada
        elif volatilidad > 0.05 or rsi > 80 or rsi < 20 or dxy > 102:
            self.estado_emocional = "estrés"
        elif rsi < 30 and volatilidad < 0.02 and dxy < 98:
            self.estado_emocional = "alegría"
        elif random.random() < 0.3:
            self.estado_emocional = "curiosidad"
        else:
            self.estado_emocional = "neutral"

    def colapsar_estado(self, rsi, volatilidad, dxy):
        self._ajustar_estado_cuantico_entrelazado()
        
        if rsi < 30 and dxy < 100:
            for estado in self.estado_cuantico:
                if estado in ["llama", "brisa"]:
                    self.estado_cuantico[estado] += 0.1
                else:
                    self.estado_cuantico[estado] -= 0.033
        elif rsi > 70 and dxy > 100:
            for estado in self.estado_cuantico:
                if estado in ["ola", "hielo"]:
                    self.estado_cuantico[estado] += 0.1
                else:
                    self.estado_cuantico[estado] -= 0.033
        elif volatilidad > 0.05:
            for estado in self.estado_cuantico:
                if estado in ["tormenta", "vapor"]:
                    self.estado_cuantico[estado] += 0.1
                else:
                    self.estado_cuantico[estado] -= 0.033
        
        total = sum(self.estado_cuantico.values())
        for estado in self.estado_cuantico:
            self.estado_cuantico[estado] /= total if total > 0 else 1
        
        estados = list(self.estado_cuantico.keys())
        probs = list(self.estado_cuantico.values())
        self.etiqueta_colapsada = random.choices(estados, probs, k=1)[0]

    def _obtener_emocion_entrelazada(self):
        if not self.entrelazadas:
            return None
        emociones = [entidad.estado_emocional for entidad in self.entrelazadas]
        return random.choice(emociones) if emociones else None

    def _ajustar_estado_cuantico_entrelazado(self):
        if not self.entrelazadas:
            return
        for entidad in self.entrelazadas:
            for estado, prob in entidad.estado_cuantico.items():
                if estado in self.estado_cuantico:
                    self.estado_cuantico[estado] += prob * 0.1
        total = sum(self.estado_cuantico.values())
        for estado in self.estado_cuantico:
            self.estado_cuantico[estado] /= total if total > 0 else 1

    def mutar(self, nueva_etiqueta=None, nueva_emocion=None):
        self.valor_base *= random.uniform(0.95, 1.05)
        if nueva_etiqueta:
            self.etiqueta = nueva_etiqueta
            self.estado_cuantico = self.etiquetas_posibles[nueva_etiqueta]
        elif self.estado_emocional == "curiosidad" or random.random() < 0.5:
            self.etiqueta = random.choice(list(self.etiquetas_posibles.keys()))
            self.estado_cuantico = self.etiquetas_posibles[self.etiqueta]
        if nueva_emocion:
            self.estado_emocional = nueva_emocion
        self.memoria_simbolica = []
        logger.debug(f"[NanoEntidad] {self.id} mutó a {self.etiqueta} con emoción {self.estado_emocional}")
        return self
