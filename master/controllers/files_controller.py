from flask import request, jsonify, Blueprint
import math
import config
import re

files_blueprint = Blueprint('files', __name__)
rc = config.get_redis()


def validate_filename(filename):
    """This allows alphanumeric characters, underscores, and hyphens, and disallows leading or trailing whitespace"""
    pattern = re.compile(r'^\s*[a-zA-Z0-9._-]+\s*$')
    return bool(pattern.match(filename))


@files_blueprint.route('/init', methods=['POST'])
def init_file():
    """
        Initializes a file in the system by creating metadata for the file in Redis.
        Sends to the client a list of servers to store the file's chunks on.
        @Params:
            filename: The name of the file to initialize.
            size: The size of the file to initialize in bytes.
        @Returns:
            200 OK if the file was successfully initialized.
            400 Bad Request if the filename is invalid or a file with the same name already exists.
            500 Internal Server Error if there are not enough healthy servers to store the file.
    """

    try:
        data = request.get_json()
    except Exception as e:
        return 'Error: Unable to parse JSON. ' + str(e), 400

    filename = data['filename']
    filesize = data['size']

    # Validate filename
    if not validate_filename(filename):
        return 'Error: Invalid filename, filename must be alphanumeric and may contain underscores and hyphens.', 400

    # Check if file with same name exists
    if rc.exists(f'file:{filename}:size'):
        return 'Error: File with same name already exists.', 400

    # Calculate number of chunks and create file metadata
    num_chunks = math.ceil(filesize / config.CHUNK_SIZE)
    rc.set(f'file:{filename}:size', filesize)
    rc.set(f'file:{filename}:chunks', num_chunks)

    # Get list of healthy servers
    healthy_server_byte_codes = rc.lrange('healthy_chunk_servers_list', 0, -1)
    if not healthy_server_byte_codes:
        return 'Error: Not enough healthy servers.', 500

    healthy_servers = [
        f"{config.CHUNK_SERVER_BASE_NAME}{int(server_byte_code)}:{config.CHUNK_SERVER_PORT}"
        for server_byte_code in healthy_server_byte_codes
    ]

    # Allocate chunks to servers
    chunk_allocations = {}
    for i in range(0, num_chunks, config.BATCH_CHUNK_SIZE):
        replication_factor = min(config.REPLICATION_FACTOR, len(healthy_servers))

        # Select servers for this batch
        batch_servers = healthy_servers[:replication_factor]

        for j in range(i, min(i + config.BATCH_CHUNK_SIZE, num_chunks)):
            # Record the servers for this chunk
            chunk_allocations[j] = [server for server in batch_servers]

        # Shift the server list for the next batch
        for _ in range(replication_factor):
            server = healthy_servers.pop(0)
            healthy_servers.append(server)

        # Send response
        return jsonify(chunk_allocations), 200

    return jsonify(chunk_allocations), 200
