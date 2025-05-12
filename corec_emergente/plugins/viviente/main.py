import json
import logging
from .symbolic_memory import SymbolicMemoryAnalyzer
from .resonance import GrafoResonancia

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PluginViviente:
    def __init__(self, nucleus):
        self.nucleus = nucleus
        self.analizador = SymbolicMemoryAnalyzer()
        self.grafo = GrafoResonancia()
        self.canal = nucleus.canal
        logger.info("[PluginViviente] Inicializado")

    async def inicializar(self):
        await self.canal.subscribe("nano_eventos", self.procesar_evento)
        logger.debug("[PluginViviente] Suscrito a nano_eventos")

    async def procesar_evento(self, mensaje):
        try:
            evento = json.loads(mensaje)
            if not self.validar_mensaje(evento):
                return

            entidad = self.buscar_entidad(evento["id"])
            if not entidad:
                return

            self.grafo.registrar_etiqueta(evento["etiqueta_colapsada"])
            for otra_entidad in self.nucleus.entidades:
                if otra_entidad.id != evento["id"]:
                    self.grafo.actualizar_resonancia(evento["etiqueta_colapsada"], otra_entidad.etiqueta_colapsada, evento["valor"])

            necesita_mutacion, nueva_etiqueta, nueva_emocion = self.analizador.analizar_memoria(entidad.memoria_simbolica)
            if necesita_mutacion:
                entidad.mutar(nueva_etiqueta, nueva_emocion)
                logger.info(f"[PluginViviente] Entidad {entidad.id} mutó a {nueva_etiqueta} con emoción {nueva_emocion}")
        except Exception as e:
            logger.error(f"[PluginViviente] Error procesando evento: {e}")

    def buscar_entidad(self, id_):
        for e in self.nucleus.entidades:
            if e.id == id_:
                return e
        return None

    def validar_mensaje(self, mensaje):
        required = ["tipo", "id", "etiqueta", "estado_cuantico", "etiqueta_colapsada", "decision", "valor", "emocion", "timestamp"]
        return all(k in mensaje for k in required) and mensaje["tipo"] == "nano_emitido"

    async def shutdown(self):
        logger.info("[PluginViviente] Apagado")
