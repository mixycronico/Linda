import pytest
import asyncio
from entities.nano import NanoEntidad
from channels import Channel

@pytest.mark.asyncio
async def test_nano_entidad_procesar():
    config = {"redis": {"host": "localhost", "port": 6379, "db": 0}}
    canal = Channel(config)
    await canal.connect()
    entidad = NanoEntidad(id="test", canal=canal)
    carga = {"precio": 50000, "rsi": 25, "sma_signal": 1, "volatilidad": 0.01, "dxy": 98}
    mensaje = await entidad.procesar(carga)
    assert mensaje["decision"] in ["comprar", "vender", "mantener"]
    assert mensaje["emocion"] in ["alegría", "estrés", "curiosidad", "neutral"]
    assert mensaje["etiqueta_colapsada"] in entidad.estado_cuantico
    await canal.shutdown()
