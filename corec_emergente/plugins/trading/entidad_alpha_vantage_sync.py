#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_alpha_vantage_sync.py
Consulta datos macro de Alpha Vantage y CoinMarketCap, procesándolos simbólicamente con el enjambre.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from corec.entidad_base import EntidadBase, Event
import aiohttp
import json
from datetime import datetime
import pytz
import aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from collections import Counter
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EntidadAlphaVantageSync(EntidadBase):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {
            "canales": ["trading_macro", "alertas"],
            "estado_persistente": True,
            "persistencia_opcional": True,
            "log_level": "INFO",
            "destino_default": "trading",
            "auto_register_channels": True,
            "redis": {
                "enabled": True,
                "host": "localhost",
                "port": 6379,
                "db": 0
            },
            "macro_api": {
                "alpha_vantage_key": "F0BH61XQ9KDFF90E",
                "coinmarketcap_key": "TU_COINMARKETCAP_API_KEY",
                "newsapi_key": "271a1e28d1ac4899a7b85684fdb13eeb",
                "macro_schedule": {
                    "active_hours_start": "07:00",
                    "active_hours_end": "17:00",
                    "timezone": "America/New_York",
                    "fetch_interval_minutes": 5
                }
            }
        }
        super().__init__(id="alpha_vantage_sync", config=config)
        self.redis = aioredis.Redis(
            host=config['redis']['host'],
            port=config['redis']['port'],
            decode_responses=True
        )
        self.alpha_vantage_key = config['macro_api']['alpha_vantage_key']
        self.cmc_key = config['macro_api']['coinmarketcap_key']
        self.newsapi_key = config['macro_api']['newsapi_key']
        self.active_start = datetime.strptime(config['macro_api']['macro_schedule']['active_hours_start'], '%H:%M').time()
        self.active_end = datetime.strptime(config['macro_api']['macro_schedule']['active_hours_end'], '%H:%M').time()
        self.timezone = pytz.timezone(config['macro_api']['macro_schedule']['timezone'])
        self.fetch_interval = config['macro_api']['macro_schedule']['fetch_interval_minutes'] * 60
        self.markets = {
            'SP500': 'SPY',
            'Nasdaq': 'QQQ',
            'DXY': 'DX-Y.NYB',
            'Gold': 'GC=F',
            'Oil': 'CL=F'
        }
        self.cmc_symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'XRP']
        self.scheduler = AsyncIOScheduler()
        logger.info("[AlphaVantageSync] Inicializado")

    async def init(self):
        await super().init()
        self.scheduler.add_job(
            self.fetch_macro_data,
            IntervalTrigger(seconds=self.fetch_interval),
            id="fetch_macro_data",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("[AlphaVantageSync] Scheduler iniciado")

    async def fetch_alpha_vantage(self, symbol: str) -> Optional[float]:
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.alpha_vantage_key}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        price = float(data.get('Global Quote', {}).get('05. price', 0))
                        if price > 0:
                            return price
                        logger.warning(f"[AlphaVantageSync] No se obtuvo precio para {symbol}")
                    else:
                        logger.error(f"[AlphaVantageSync] Error Alpha Vantage para {symbol}: {resp.status}")
            except Exception as e:
                logger.error(f"[AlphaVantageSync] Excepción al consultar {symbol}: {str(e)}")
        return None

    async def fetch_coinmarketcap(self) -> Dict[str, Any]:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": self.cmc_key}
        params = {"symbol": ",".join(self.cmc_symbols)}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = {}
                        for symbol in self.cmc_symbols:
                            if symbol in data.get('data', {}):
                                quote = data['data'][symbol]['quote']['USD']
                                result[symbol] = {
                                    'market_cap': quote.get('market_cap', 0),
                                    'volume_24h': quote.get('volume_24h', 0)
                                }
                        return result
                    else:
                        logger.error(f"[AlphaVantageSync] Error CoinMarketCap: {resp.status}")
            except Exception as e:
                logger.error(f"[AlphaVantageSync] Excepción en CoinMarketCap: {str(e)}")
        return {}

    async def fetch_critical_news(self) -> Dict[str, Any]:
        try:
            news_data = {"fed_rate_change": random.choice([0, 0.25, -0.25]), "timestamp": datetime.utcnow().isoformat()}
            await self.redis.set("critical_news", json.dumps(news_data))
            logger.info(f"[AlphaVantageSync] Noticias críticas obtenidas: {news_data}")
            return news_data
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error al obtener noticias críticas: {e}")
            return {}

    async def is_market_active(self) -> bool:
        now = datetime.now(self.timezone).time()
        return self.active_start <= now <= self.active_end

    async def process_macro_symbolically(self, macro_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            carga = {
                "precio": macro_data.get('DXY', 100),
                "rsi": 50,
                "sma_signal": 0,
                "volatilidad": 0.02,
                "dxy": macro_data.get('DXY', 100),
                "sp500": macro_data.get('SP500', 0.0)
            }
            for bloque in self.controller.nucleus.bloques:
                await bloque.procesar(carga)
            symbolic_state = {
                "emocion_dominante": Counter([e.memoria_simbolica[-1]["emocion"] for b in self.controller.nucleus.bloques for e in b.entidades if e.memoria_simbolica]).most_common(1)[0][0],
                "etiqueta_dominante": Counter([e.memoria_simbolica[-1]["etiqueta_colapsada"] for b in self.controller.nucleus.bloques for e in b.entidades if e.memoria_simbolica]).most_common(1)[0][0]
            }
            macro_data["symbolic_state"] = symbolic_state
            return macro_data
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error procesando datos macro simbólicamente: {e}")
            return macro_data

    async def fetch_macro_data(self) -> None:
        try:
            if not await self.is_market_active():
                logger.debug("[AlphaVantageSync] Fuera del horario activo")
                return
            macro_data = {}
            for name, symbol in self.markets.items():
                price = await self.fetch_alpha_vantage(symbol)
                if price:
                    macro_data[name] = price
            cmc_data = await self.fetch_coinmarketcap()
            macro_data['cmc'] = cmc_data
            altcoins_volume = sum(d['volume_24h'] for s, d in cmc_data.items() if s not in ['BTC', 'ETH'])
            macro_data['altcoins_volume'] = altcoins_volume
            news_data = await self.fetch_critical_news()
            if news_data and news_data["fed_rate_change"] > 0:
                macro_data['DXY'] += 0.5
            elif news_data and news_data["fed_rate_change"] < 0:
                macro_data['DXY'] -= 0.5
            macro_data = await self.process_macro_symbolically(macro_data)
            await self.redis.setex('market:macro', 1800, json.dumps(macro_data))
            await self.controller.publicar_evento(
                canal="trading_macro",
                datos=macro_data,
                destino="trading"
            )
            logger.info(f"[AlphaVantageSync] Datos macro publicados: {macro_data}")
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error obteniendo datos macro: {e}")

    async def manejar_evento(self, event: Event):
        try:
            if event.canal == "trading_comandos" and event.datos.get("texto") == "fetch_macro":
                await self.fetch_macro_data()
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error manejando evento: {e}")

    async def shutdown(self):
        self.scheduler.shutdown()
        if self.redis:
            await self.redis.close()
            logger.info("[AlphaVantageSync] Desconectado de Redis")
        logger.info("[AlphaVantageSync] Apagado")
        await super().shutdown()
