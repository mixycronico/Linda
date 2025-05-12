from collections import Counter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SymbolicMemoryAnalyzer:
    def __init__(self):
        self.max_memoria = 10

    def analizar_memoria(self, memoria_simbolica):
        if not memoria_simbolica:
            return False, None, None

        decisiones = [e["decision"] for e in memoria_simbolica]
        emociones = [e["emocion"] for e in memoria_simbolica]
        valores = [e["valor"] for e in memoria_simbolica]
        decision_counts = Counter(decisiones)
        emocion_counts = Counter(emociones)
        valor_promedio = sum(valores) / len(valores) if valores else 0

        necesita_mutacion = False
        nueva_etiqueta = None
        nueva_emocion = None

        if decision_counts["vender"] > 5 and "estrés" in emociones and valor_promedio > 0.7:
            necesita_mutacion = True
            nueva_etiqueta = "agua"
            nueva_emocion = "neutral"
        elif decision_counts["comprar"] > 5 and "alegría" in emociones and valor_promedio < 0.3:
            necesita_mutacion = True
            nueva_etiqueta = "viento"
            nueva_emocion = "curiosidad"
        elif decision_counts["mantener"] > 7 and "curiosidad" in emociones and valor_promedio > 0.5:
            necesita_mutacion = True
            nueva_etiqueta = "tierra"
            nueva_emocion = "neutral"

        logger.debug(f"[SymbolicMemoryAnalyzer] Análisis: necesita_mutacion={necesita_mutacion}, etiqueta={nueva_etiqueta}, emoción={nueva_emocion}")
        return necesita_mutacion, nueva_etiqueta, nueva_emocion
