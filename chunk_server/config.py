import os
import redis


def get_redis() -> redis.Redis:
    return redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT')),
        db=int(os.getenv('REDIS_DB')),
        password=os.getenv('REDIS_PASSWORD')
    )


UPLOAD_FOLDER = '/chunks'
CHUNK_SERVER_ID = int(os.getenv("CHUNK_SERVER_ID"))
CHUNK_SERVER_PORT = 5000
CHUNK_SERVER_BASE_NAME = "chunk_server_"
