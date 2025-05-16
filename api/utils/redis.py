import redis.asyncio as redis
import os

redisClient = redis.from_url(os.environ.get("REDIS_URL"), decode_responses=True)
