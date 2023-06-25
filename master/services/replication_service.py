import config
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from time import sleep

rc = config.get_redis()


def preflight_check(server, filename, chunk_id):
    """
    Perform a preflight check to see if a server has a specific chunk.
    Return True if the server has the chunk, False otherwise.
    """
    try:
        response = requests.head(f'http://{server}/retrieve/{filename}/{chunk_id}')
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def replication():
    while True:
        sleep(10)  # Sleep for 60 seconds

        # Get list of all files
        files_byte_codes = rc.keys(pattern='file:*:size')
        files = [file.decode().split(':')[1] for file in files_byte_codes]

        for filename in files:
            num_chunks = int(rc.get(f'file:{filename}:chunks').decode())
            for chunk_id in range(num_chunks):
                chunk_servers_bytes = rc.lrange(f'file:{filename}:chunks:{chunk_id}:chunk_servers', 0, -1)
                chunk_servers = [server.decode() for server in chunk_servers_bytes]

                valid_servers = [server for server in chunk_servers if preflight_check(server, filename, chunk_id)]
                invalid_servers = set(chunk_servers) - set(valid_servers)

                # Check if the chunk needs to be replicated (if there is no valid server do not remove from redis
                # since that will make the chunk unavailable forever, instead leave it as it is and hope that some
                # server will come back online)
                if len(valid_servers) and len(valid_servers) < config.REPLICATION_FACTOR:

                    # Retrieve the chunk from a valid server
                    chunk = requests.get(f'http://{valid_servers[0]}/retrieve/{filename}/{chunk_id}')

                    # Remove invalid servers from chunk's server list in Redis
                    for invalid_server in invalid_servers:
                        rc.lrem(f'file:{filename}:chunks:{chunk_id}:chunk_servers', 0, invalid_server)

                    # Replicate the chunk to other servers
                    healthy_server_byte_codes = rc.lrange('healthy_chunk_servers_list', 0, -1)
                    healthy_servers = [
                        f"{config.CHUNK_SERVER_BASE_NAME}{int(server_byte_code)}:{config.CHUNK_SERVER_PORT}"
                        for server_byte_code in healthy_server_byte_codes
                    ]

                    for server in healthy_servers:
                        if len(valid_servers) < config.REPLICATION_FACTOR and server not in valid_servers:
                            try:
                                # The chunk needs to be replicated on this server
                                m = MultipartEncoder(
                                    fields={'file': ('filename', chunk.content)}
                                )
                                response = requests.post(
                                    f'http://{server}/store/{filename}/{chunk_id}',
                                    data=m,
                                    headers={'Content-Type': m.content_type}
                                )

                                if response.status_code == 200:
                                    # If replication was successful, update Redis
                                    rc.rpush(f'file:{filename}:chunks:{chunk_id}:chunk_servers', server)

                                    # Log the replication
                                    print(f'Chunk {chunk_id} of file {filename} has been replicated to {server}')

                                    # Add the server to the list of valid servers
                                    valid_servers.append(server)

                                if len(valid_servers) >= config.REPLICATION_FACTOR:
                                    # If the chunk has been replicated enough times, break the loop
                                    break

                            except requests.exceptions.ConnectionError:
                                # If the server is not available, continue to the next server
                                continue
