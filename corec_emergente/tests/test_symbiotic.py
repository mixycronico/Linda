import pytest
import asyncio
from blocks.symbiotic import BloqueSimbiotico
from entities.nano import NanoEntidad
from channels import Channel

@pytest.mark.asyncio
async def test_bloque_simbiotico_procesar():
    config = {"redis": {"host": "localhost", "port": 6379, "db": 0}, "capital": 10000, "memoria_max": 50}
    canal = Channel(config)
    await canal.connect()
    entidades = [NanoEntidad(id=f"ent{i}", canal=canal) for i in range(3)]
    bloque = BloqueSimbiotico(id="bloque1", entidades=entidades, canal=canal, config=config)
    carga = {"precio": 50000, "rsi": 25, "sma_signal": 1, "volatilidad": 0.01, "dxy": 98}
    fitness = await bloque.procesar(carga)
    assert isinstance(fitness, float)
    await canal.shutdown()
