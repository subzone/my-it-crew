import redis
from src.config import Settings

redis_client = redis.Redis(host=Settings().redis_host, port=Settings().redis_port, password=Settings().redis_password, db=Settings().redis_db)