import pytest
import asyncio
from nucleus import Nucleus
from plugins.viviente.main import PluginViviente
from entities.nano import NanoEntidad
from channels import Channel

@pytest.mark.asyncio
async def test_plugin_viviente_procesar():
    config = {"redis": {"host": "localhost", "port": 6379, "db": 0}}
    nucleus = Nucleus(config)
    canal = Channel(config)
    await canal.connect()
    entidad = NanoEntidad(id="test", canal=canal)
    nucleus.entidades.append(entidad)
    plugin = PluginViviente(nucleus)
    await plugin.inicializar()
    carga = {"precio": 50000, "rsi": 25, "sma_signal": 1, "volatilidad": 0.01, "dxy": 98}
    evento = await entidad.procesar(carga)
    await plugin.procesar_evento(json.dumps(evento))
    assert len(plugin.grafo.etiquetas) > 0
    await plugin.shutdown()
    await canal.shutdown()
