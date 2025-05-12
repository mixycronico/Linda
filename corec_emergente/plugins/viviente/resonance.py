import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GrafoResonancia:
    def __init__(self):
        self.relaciones = {}
        self.etiquetas = set()

    def registrar_etiqueta(self, etiqueta):
        self.etiquetas.add(etiqueta)

    def actualizar_resonancia(self, etiqueta1, etiqueta2, impacto):
        clave = tuple(sorted([etiqueta1, etiqueta2]))
        self.relaciones[clave] = self.relaciones.get(clave, 1.0) * (1 + impacto * 0.1)
        if self.relaciones[clave] > 2.0:
            self.relaciones[clave] = 2.0
        elif self.relaciones[clave] < 0.5:
            self.relaciones[clave] = 0.5
        logger.debug(f"[GrafoResonancia] Resonancia actualizada: {clave} -> {self.relaciones[clave]}")

    def calcular_impacto(self, etiqueta1, etiqueta2):
        clave = tuple(sorted([etiqueta1, etiqueta2]))
        return self.relaciones.get(clave, 1.0)

    async def sugerir_mutacion(self, etiqueta_actual, contexto):
        if contexto.get("anomalia_detectada"):
            posibles = list(self.etiquetas - {etiqueta_actual})
            return random.choice(posibles) if posibles else etiqueta_actual
        return etiqueta_actual
