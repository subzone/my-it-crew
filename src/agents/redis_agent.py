import redis

def connect_redis(host, port, password, db):
    try:
        client = redis.Redis(host=host, port=port, password=password, db=db)
        client.ping()
        return client
    except redis.exceptions.ConnectionError as e:
        print(f"Error connecting to Redis: {e}")
        return None