from flask import Flask, request, Response, jsonify
import requests
import os
import config

app = Flask(__name__)


@app.route('/files/<filename>', methods=['POST'])
def upload(filename: str):
    """Upload a file to the distributed file system. The file is split into chunks and stored
    on the chunk servers. The file is replicated on multiple chunk servers. The master server
    keeps track of which chunks are stored on which chunk servers.
    :param filename: The name of the file
    :return: A JSON response with a message if the file was uploaded successfully"""
    if 'file' not in request.files:
        return jsonify({'error': 'Bad request: No file sent'}), 400

    file = request.files['file']

    # Calculate file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer

    # Initialize the file on the master server
    init_data = {'filename': filename, 'size': file_size}
    init_response = requests.post(f'{config.MASTER_URL}/v1/files/init', json=init_data)
    if init_response.status_code != 200:
        return jsonify({"error": f"Error initializing file on master server: {init_response.json()['error']}"}), init_response.status_code

    chunk_allocations = init_response.json()

    # Split file into chunks and upload to chunk servers
    chunk_size = config.CHUNK_SIZE
    for chunk_id, servers in chunk_allocations.items():
        file_chunk = file.read(chunk_size)

        for server in servers:
            chunk_data = {'file': (filename, file_chunk)}
            store_response = requests.post(f'http://{server}/store/{filename}/{chunk_id}', files=chunk_data)

            if store_response.status_code != 200:
                return jsonify({"error": f"Error storing file chunk on chunk server : {store_response.json()['error']}"}), 500

    return jsonify({'message': 'File uploaded successfully'}), 200


@app.route('/files/<filename>', methods=['GET'])
def download(filename: str):
    """Download a file from the distributed file system. The file is retrieved from the chunk servers
    and reassembled into the original file.
    :param filename: The name of the file
    :return: A JSON response with a message if the file was downloaded successfully"""
    # Get chunk locations from master server
    chunk_response = requests.get(f'{config.MASTER_URL}/v1/files/{filename}/chunks')
    if chunk_response.status_code != 200:
        return jsonify({"error": f"Error retrieving chunk locations from master server: {chunk_response.json()['error']}"}), chunk_response.status_code

    chunk_locations = chunk_response.json()

    # Preflight check for all chunk servers
    for chunk_id, servers in chunk_locations.items():
        if not any(is_chunk_available(server, filename, chunk_id) for server in servers):
            return jsonify({"error": f"Unable to retrieve chunk {chunk_id} from all chunk servers"}), 500

    # Actual streaming
    def generate():
        # Stream each chunk from chunk servers
        for chunk_id, servers in chunk_locations.items():
            for server in servers:
                try:
                    retrieve_response = requests.get(f'http://{server}/retrieve/{filename}/{chunk_id}', stream=True)
                    if retrieve_response.status_code == 200:
                        yield from retrieve_response.iter_content(chunk_size=config.CHUNK_SIZE)
                        break
                except requests.exceptions.RequestException:
                    continue

    response = Response(generate(), mimetype='application/octet-stream')
    response.headers.set('Content-Disposition', 'attachment', filename=filename)
    return response


def is_chunk_available(server, filename, chunk_id):
    """Check if a chunk is available on a chunk server by sending a HEAD request to the chunk server
    :param server: The chunk server (host:port)
    :param filename: The name of the file
    :param chunk_id: The id of the chunk in the file
    :return: True if the chunk is available, False otherwise"""
    try:
        retrieve_response = requests.head(f'http://{server}/retrieve/{filename}/{chunk_id}')
        return retrieve_response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@app.route('/files/<filename>', methods=['DELETE'])
def delete(filename: str):
    """Delete a file from the distributed file system. The file is deleted from the chunk servers.
    The master server is updated to reflect the deletion.
    :param filename: The name of the file
    :return: A JSON response with a message if the file was deleted successfully"""
    # Get chunk locations from master server
    chunk_response = requests.get(f'{config.MASTER_URL}/v1/files/{filename}/chunks')
    if chunk_response.status_code != 200:
        return jsonify({"error": f"Error retrieving chunk locations from master server: {chunk_response.json()['error']}"}), chunk_response.status_code

    chunk_locations = chunk_response.json()

    # Delete each chunk from chunk servers
    for chunk_id, servers in chunk_locations.items():
        for server in servers:
            try:
                delete_response = requests.delete(f'http://{server}/delete/{filename}/{chunk_id}')

                if delete_response.status_code != 200 and delete_response.status_code != 404:
                    return jsonify({"error": f'Error deleting file chunk {chunk_id} from chunk server {server}'}), 500
            except requests.exceptions.RequestException:
                continue

    # Delete file from master server
    delete_master_response = requests.delete(f'{config.MASTER_URL}/v1/files/{filename}')
    if delete_master_response.status_code != 200:
        return jsonify({"error": f"Error deleting file from master server: {delete_master_response.json()['error']}"}), 500

    return jsonify({'message': 'Filed deleted succesfully'}), 200


@app.route('/files/<filename>/size', methods=['GET'])
def size(filename: str):
    """Get the size of a file from the distributed file system. The size is retrieved from the master server.
    :param filename: The name of the file
    :return: A JSON response with the size of the file"""
    size_response = requests.get(f'{config.MASTER_URL}/v1/files/{filename}/size')
    return size_response.json(), size_response.status_code


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'message': 'healthy'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
