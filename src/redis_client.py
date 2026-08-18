import redis

cache = redis.Redis(host='localhost', port=6379, db=0)
