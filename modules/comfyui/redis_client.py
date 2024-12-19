from typing import Optional, Dict, Any
import json
from datetime import datetime, timedelta

import redis.asyncio as redis
from loguru import logger


class ComfyUIRedisClient:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.redis_url = f"redis://{host}:{port}/{db}"
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis if not already connected"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(self.redis_url)

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None

    async def set_task_status(
        self, prompt_id: str, status: str, data: Optional[Dict] = None
    ):
        """Set task status and optional data in Redis"""
        await self.connect()
        task_data = {
            "status": status,
            "updated_at": datetime.now().isoformat(),
            "data": data,
        }
        await self.redis_client.set(
            f"comfyui:task:{prompt_id}",
            json.dumps(task_data),
            ex=timedelta(hours=24),  # expire after 24 hours
        )

    async def get_task_status(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get task status and data from Redis"""
        await self.connect()
        result = await self.redis_client.get(f"comfyui:task:{prompt_id}")
        if result:
            return json.loads(result)
        return None

    async def cache_image_result(self, prompt_id: str, node_id: str, image_data: bytes):
        """Cache image result in Redis"""
        await self.connect()
        key = f"comfyui:image:{prompt_id}:{node_id}"
        await self.redis_client.set(
            key, image_data, ex=timedelta(hours=1)
        )  # expire after 1 hour

    async def get_cached_image(self, prompt_id: str, node_id: str) -> Optional[bytes]:
        """Get cached image from Redis"""
        await self.connect()
        key = f"comfyui:image:{prompt_id}:{node_id}"
        return await self.redis_client.get(key)
