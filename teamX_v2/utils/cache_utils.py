from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)

async def setup_redis(host: str = "localhost", port: int = 6379, db: int = 0) -> Redis:
    try:
        redis_client = Redis(host=host, port=port, db=db, decode_responses=True)
        await redis_client.ping()
        logger.info("Successfully connected to Redis")
        return redis_client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise