import pytest
import asyncio
from nucleus import Nucleus, SistemaTradingTradicional

@pytest.mark.asyncio
async def test_nucleus_simular():
    config = {"redis": {"host": "localhost", "port": 6379, "db": 0}, "memoria_max_global": 50}
    nucleus = Nucleus(config)
    await nucleus.simular(ciclos=10)
    assert len(nucleus.precios) == 10
    assert len(nucleus.memoria_global) <= 50
    await nucleus.shutdown()
