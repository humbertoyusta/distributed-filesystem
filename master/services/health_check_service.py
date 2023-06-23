import config
from time import sleep
import requests


def health_check():
    rc = config.get_redis()

    while True:
        sleep(10)

        for chunk_server_id_bytes in rc.smembers('chunk_servers'):
            chunk_server_id = int(chunk_server_id_bytes)
            try:
                requests.get(f'http://{config.CHUNK_SERVER_BASE_NAME}{chunk_server_id}:5000/health')

                if rc.sadd('healthy_chunk_servers_set', chunk_server_id):
                    rc.rpush('healthy_chunk_servers_list', chunk_server_id)

                print(f'Chunk server {chunk_server_id} is healthy')
            except requests.exceptions.ConnectionError:
                if rc.srem('healthy_chunk_servers_set', chunk_server_id):
                    rc.lrem('healthy_chunk_servers_list', 0, chunk_server_id)

                print(f'Chunk server {chunk_server_id} is unhealthy')
