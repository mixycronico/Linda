import aioredis
import json
import logging
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Channel:
    def __init__(self, redis_config):
        self.redis_config = redis_config
        self.redis = None
        self.pubsub = None
        self.subscribers = {}
        self.nucleus = None  # Referencia al núcleo para acceso a plugins

    async def connect(self):
        try:
            self.redis = await aioredis.create_redis_pool(
                f"redis://{self.redis_config['host']}:{self.redis_config['port']}/{self.redis_config['db']}"
            )
            self.pubsub = self.redis.pubsub()
            logger.info("[Channel] Conectado a Redis")
        except Exception as e:
            logger.error(f"[Channel] Error conectando a Redis: {e}")
            raise

    async def publish(self, channel, message):
        try:
            await self.redis.publish(channel, message)
            logger.debug(f"[Channel] Publicado en {channel}: {message}")
        except Exception as e:
            logger.error(f"[Channel] Error publicando en {channel}: {e}")

    async def subscribe(self, channel, callback):
        if channel not in self.subscribers:
            self.subscribers[channel] = []
            await self.pubsub.subscribe(channel)
            asyncio.create_task(self._listen(channel))
        self.subscribers[channel].append(callback)
        logger.debug(f"[Channel] Suscrito a {channel}")

    async def _listen(self, channel):
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    data = message["data"].decode()
                    for callback in self.subscribers.get(channel, []):
                        await callback(data)
        except Exception as e:
            logger.error(f"[Channel] Error escuchando en {channel}: {e}")

    async def shutdown(self):
        if self.pubsub:
            await self.pubsub.unsubscribe()
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
        logger.info("[Channel] Desconectado de Redis")
