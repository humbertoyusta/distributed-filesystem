import config
from time import sleep
import requests


def health_check():
    """Health check service that checks the health of all chunk servers every 10 seconds
    and updates the 'healthy_chunk_servers_set' and 'healthy_chunk_servers_list' accordingly."""
    rc = config.get_redis()

    while True:
        sleep(10)

        for chunk_server_id_bytes in rc.smembers('chunk_servers'):
            chunk_server_id = int(chunk_server_id_bytes.decode())
            try:
                requests.get(f'http://{config.CHUNK_SERVER_BASE_NAME}{chunk_server_id}:5000/health')

                # Watching the 'healthy_chunk_servers_set' key
                rc.watch('healthy_chunk_servers_set')
                if chunk_server_id_bytes not in rc.smembers('healthy_chunk_servers_set'):
                    pipeline = rc.pipeline()
                    pipeline.multi()
                    pipeline.sadd('healthy_chunk_servers_set', chunk_server_id)
                    pipeline.rpush('healthy_chunk_servers_list', chunk_server_id)
                    pipeline.execute()

                print(f'Chunk server {chunk_server_id} is healthy')
            except requests.exceptions.ConnectionError:
                # Watching the 'healthy_chunk_servers_set' key
                rc.watch('healthy_chunk_servers_set')
                if chunk_server_id_bytes in rc.smembers('healthy_chunk_servers_set'):
                    pipeline = rc.pipeline()
                    pipeline.multi()
                    pipeline.srem('healthy_chunk_servers_set', chunk_server_id)
                    pipeline.lrem('healthy_chunk_servers_list', 0, chunk_server_id)
                    pipeline.execute()

                print(f'Chunk server {chunk_server_id} is unhealthy')
            finally:
                rc.unwatch()
