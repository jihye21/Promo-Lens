import os
import json
import redis
import logging
from pathlib import Path

logger = logging.getLogger("lotte-fallback")

class LocalFallbackCircuitBreaker:
    def __init__(self, redis_url: str = None):
        if not redis_url:
            redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        
        logger.info(f"Connecting to Redis at: {redis_url}")
        
        self.redis_client = redis.Redis.from_url(redis_url, socket_timeout=3.0, socket_connect_timeout=3.0)
        self.fallback_file = Path("/tmp/lotte_fallback_audit_buffer.jsonl")

    def push_audit_event(self, event_data: dict) -> bool:
        try:
            self.redis_client.ping()
            self.redis_client.xadd("lotte:audit:stream", {"data": json.dumps(event_data)})
            return True
        except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
            logger.warning(f"Redis connection issue: {str(e)}. Writing to Local Fallback File.")
            try:
                with open(self.fallback_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event_data) + "\n")
                return True
            except Exception as file_err:
                logger.critical(f"FATAL: Local fallback write failed: {str(file_err)}")
                return False