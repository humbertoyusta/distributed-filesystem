import os
import redis


def get_redis() -> redis.Redis:
    return redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT')),
        db=int(os.getenv('REDIS_DB')),
        password=os.getenv('REDIS_PASSWORD')
    )


CHUNK_SERVER_NUMBER = os.getenv("CHUNK_SERVER_NUMBER")

CHUNK_SERVER_BASE_NAME = "chunk_server_"
CHUNK_SERVER_PORT = 5000

CHUNK_SIZE = os.getenv("CHUNK_SIZE") if os.getenv("CHUNK_SIZE") else 1024 # 1KB

REPLICATION_FACTOR = os.getenv("REPLICATION_FACTOR") if os.getenv("REPLICATION_FACTOR") else 2

BATCH_CHUNK_SIZE = os.getenv("BATCH_CHUNK_SIZE") if os.getenv("BATCH_CHUNK_SIZE") else 10 # Number of chunks
# to be sent to same chunk server in one step of round robin for upload
