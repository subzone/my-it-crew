import redis

def connect_to_redis(host, port, password, database):
    # Establish connection to Redis instance
    client = redis.Redis(host=host, port=port, password=password, db=database)
    return client

def health_check(client):
    # Health check endpoint (/redis/ping) returns PONG
    return client.ping() == b'PONG'
