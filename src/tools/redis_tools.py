# Redis tooling for My IT Crew

import redis
from src.config import Settings

settings = Settings()

redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, password=settings.redis_password, db=settings.redis_db)
