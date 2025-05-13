#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entidad_alpha_vantage_sync.py
Consulta datos macro de Alpha Vantage y CoinMarketCap, procesándolos simbólicamente.
Opera de 7:00 AM a 5:00 PM (UTC-4), cada 5 minutos.
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
            "redis": {"host": "localhost", "port": 6379, "db": 0},
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
        logger.info("[AlphaVantageSync] Inicializado")

    async def init(self):
        await super().init()
        asyncio.create_task(self.run_macro_fetch())

    async def fetch_alpha_vantage(self, symbol: str) -> Optional[float]:
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.alpha_vantage_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        price = float(data.get('Global Quote', {}).get('05. price', 0))
                        if price > 0:
                            return price
                        logger.warning(f"[AlphaVantageSync] No se obtuvo precio para {symbol}")
                    else:
                        logger.error(f"[AlphaVantageSync] Error Alpha Vantage para {symbol}: {resp.status}")
            return None
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Excepción al consultar {symbol}: {str(e)}")
            return None

    async def fetch_coinmarketcap(self) -> Dict[str, Any]:
        try:
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {"X-CMC_PRO_API_KEY": self.cmc_key}
            params = {"symbol": ",".join(self.cmc_symbols)}
            async with aiohttp.ClientSession() as session:
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
            return {}
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Excepción en CoinMarketCap: {str(e)}")
            return {}

    async def fetch_news_sentiment(self) -> float:
        try:
            url = f"https://newsapi.org/v2/everything?q=cryptocurrency&apiKey={self.newsapi_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return 0.5  # Neutral, bajo peso
                    else:
                        logger.error(f"[AlphaVantageSync] Error NewsAPI: {resp.status}")
            return 0.5
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Excepción en NewsAPI: {str(e)}")
            return 0.5

    async def is_market_active(self) -> bool:
        try:
            now = datetime.now(self.timezone).time()
            return self.active_start <= now <= self.active_end
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error verificando horario activo: {e}")
            return False

    async def fetch_macro_data(self) -> Dict[str, Any]:
        try:
            macro_data = {}
            for name, symbol in self.markets.items():
                price = await self.fetch_alpha_vantage(symbol)
                if price:
                    macro_data[name] = price

            cmc_data = await self.fetch_coinmarketcap()
            macro_data['cmc'] = cmc_data
            altcoins_volume = sum(d['volume_24h'] for s, d in cmc_data.items() if s not in ['BTC', 'ETH'])
            macro_data['altcoins_volume'] = altcoins_volume

            news_sentiment = await self.fetch_news_sentiment()
            macro_data['news_sentiment'] = news_sentiment

            # Procesar simbólicamente para el enjambre
            macro_data['etiqueta_simbolica'] = "tierra" if macro_data.get('DXY', 100) > 100 else "fuego"
            macro_data['emocion_simbolica'] = "estrés" if macro_data.get('DXY', 100) > 100 else "alegría"
            return macro_data
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error obteniendo datos macro: {e}")
            return {}

    async def save_macro_metrics(self, macro_data: Dict[str, Any]) -> None:
        if self._use_postgres:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        '''
                        INSERT INTO macro_metrics (sp500_price, nasdaq_price, dxy_price, gold_price, oil_price,
                                                   btc_market_cap, eth_market_cap, altcoins_volume, news_sentiment, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ''',
                        macro_data.get('SP500', 0.0), macro_data.get('Nasdaq', 0.0), macro_data.get('DXY', 0.0),
                        macro_data.get('Gold', 0.0), macro_data.get('Oil', 0.0),
                        macro_data.get('cmc', {}).get('BTC', {}).get('market_cap', 0.0),
                        macro_data.get('cmc', {}).get('ETH', {}).get('market_cap', 0.0),
                        macro_data.get('altcoins_volume', 0.0), macro_data.get('news_sentiment', 0.5),
                        datetime.utcnow()
                    )
                logger.debug("[AlphaVantageSync] Métricas macro guardadas en PostgreSQL")
            except Exception as e:
                logger.error(f"[AlphaVantageSync] Error guardando métricas macro: {e}")

    async def run_macro_fetch(self):
        try:
            while not self._shutdown:
                if await self.is_market_active():
                    macro_data = await self.fetch_macro_data()
                    if macro_data:
                        await self.redis.setex('market:macro', 1800, json.dumps(macro_data))
                        await self.controller.publicar_evento(
                            canal="trading_macro",
                            datos=macro_data,
                            destino="trading"
                        )
                        await self.save_macro_metrics(macro_data)
                        logger.info(f"[AlphaVantageSync] Datos macro publicados: {macro_data}")
                    else:
                        logger.warning("[AlphaVantageSync] No se obtuvieron datos macro")
                else:
                    logger.debug("[AlphaVantageSync] Fuera del horario activo, esperando...")
                await asyncio.sleep(self.fetch_interval)
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error ejecutando fetch macro: {e}")

    async def manejar_evento(self, event: Event):
        try:
            if event.canal == "trading_comandos" and event.datos.get("texto") == "fetch_macro":
                macro_data = await self.fetch_macro_data()
                await self.controller.publicar_evento(
                    canal="trading_macro",
                    datos=macro_data,
                    destino="trading"
                )
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error manejando evento: {e}")

    async def shutdown(self):
        try:
            if self.redis:
                await self.redis.close()
                logger.info("[AlphaVantageSync] Desconectado de Redis")
            logger.info("[AlphaVantageSync] Apagado")
            await super().shutdown()
        except Exception as e:
            logger.error(f"[AlphaVantageSync] Error apagando: {e}")
