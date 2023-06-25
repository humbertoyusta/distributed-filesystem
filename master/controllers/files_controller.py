import requests
from flask import request, jsonify, Blueprint
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
    """Initializes a file in the system by creating metadata for the file in Redis.
    Sends to the client a list of servers to store the file's chunks on.
    Request param filename: The name of the file
    Request param size: The size of the file in bytes
    :return: A JSON response with a list of servers to store the file's chunks on"""
    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({'error': 'Unable to parse JSON.', 'details': str(e)}), 400

    filename = data['filename']
    filesize = data['size']

    # Validate filename
    if not validate_filename(filename):
        return jsonify({'error': 'Invalid filename, filename must be alphanumeric and may contain underscores and hyphens.'}), 400

    # Check if file with same name exists
    if rc.exists(f'file:{filename}:size'):
        return jsonify({'error': 'File with same name already exists.'}), 400

    # Calculate number of chunks and create file metadata
    num_chunks = ((filesize + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE) # Round up
    rc.set(f'file:{filename}:size', filesize)
    rc.set(f'file:{filename}:chunks', num_chunks)

    # Get list of healthy servers
    healthy_server_byte_codes = rc.lrange('healthy_chunk_servers_list', 0, -1)
    if not healthy_server_byte_codes:
        return jsonify({'error': 'Not enough healthy servers.'}), 500

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
            healthy_servers.append(healthy_servers.pop(0))

        # Shift the redis list
        for _ in range(replication_factor):
            rc.rpush('healthy_chunk_servers_list', rc.lpop('healthy_chunk_servers_list'))

    return jsonify(chunk_allocations), 200


@files_blueprint.route('/<filename>/size', methods=['GET'])
def get_file_size(filename: str):
    """Gets the size of a file in the system. Returns 404 if the file does not exist.
    :param filename: The name of the file
    :return: A JSON response with the size of the file in bytes"""
    if not validate_filename(filename) or not rc.exists(f'file:{filename}:size'):
        return jsonify({'error': 'File does not exist.'}), 404
    size = rc.get(f'file:{filename}:size')
    return jsonify({'size': size.decode()}), 200


@files_blueprint.route('/<filename>/chunks', methods=['GET'])
def get_chunks(filename: str):
    """Gets the locations of all chunks of a file in the system. Returns 404 if the file does not exist.
    :param filename: The name of the file
    :return: A JSON response with the locations of all chunks of the file"""
    if not validate_filename(filename):
        return jsonify({'error': 'Invalid filename.'}), 400
    if not rc.exists(f'file:{filename}:chunks'):
        return jsonify({'error': 'File does not exist.'}), 404

    num_chunks = int(rc.get(f'file:{filename}:chunks'))
    chunk_locations = {}

    for chunk_id in range(num_chunks):
        chunk_servers_bytes = rc.smembers(f'file:{filename}:chunks:{chunk_id}:chunk_servers')
        chunk_servers = [
            server.decode()
            for server in chunk_servers_bytes
        ]
        chunk_locations[chunk_id] = chunk_servers

    return jsonify(chunk_locations), 200


@files_blueprint.route('/<filename>', methods=['DELETE'])
def delete_file(filename: str):
    """Deletes a file from the system. Returns 404 if the file does not exist.
    Returns 400 if the file cannot be deleted because some chunks are not deleted.
    :param filename: The name of the file
    :return: A JSON response with the size of the file in bytes"""
    if not validate_filename(filename):
        return jsonify({'error': 'Invalid filename.'}), 400

    # Check if file exists
    if not rc.exists(f'file:{filename}:size'):
        return jsonify({'error': 'File does not exist.'}), 404

    # Check if all chunks are deleted
    num_chunks = int(rc.get(f'file:{filename}:chunks').decode())
    for chunk_id in range(num_chunks):
        chunk_server_set_key = f'file:{filename}:chunks:{chunk_id}:chunk_servers'
        if rc.exists(chunk_server_set_key):
            chunk_servers_bytes = rc.smembers(chunk_server_set_key)
            chunk_servers = [server.decode() for server in chunk_servers_bytes]

            for server in chunk_servers:
                if preflight_check(server, filename, chunk_id):
                    return jsonify({'error': 'File cannot be deleted. Some chunks are not deleted.'}), 400

            # If none of the servers contain the chunk, delete the chunk's server list from Redis
            rc.delete(chunk_server_set_key)

    # Delete file metadata
    rc.delete(f'file:{filename}:size')
    rc.delete(f'file:{filename}:chunks')

    return jsonify({'message': 'File deleted successfully'}), 200


def preflight_check(server, filename, chunk_id):
    """Perform a preflight check to see if a server has a specific chunk.
    Return True if the server has the chunk, False otherwise."""
    try:
        response = requests.head(f'http://{server}/retrieve/{filename}/{chunk_id}')
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False

