from flask import Flask, request, Response, jsonify
import requests
import os
import config

app = Flask(__name__)


@app.route('/files/<filename>', methods=['POST'])
def upload(filename: str):
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
def download(filename):
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
                retrieve_response = requests.get(f'http://{server}/retrieve/{filename}/{chunk_id}', stream=True)
                if retrieve_response.status_code == 200:
                    yield from retrieve_response.iter_content(chunk_size=config.CHUNK_SIZE)
                    break

    response = Response(generate(), mimetype='application/octet-stream')
    response.headers.set('Content-Disposition', 'attachment', filename=filename)
    return response


def is_chunk_available(server, filename, chunk_id):
    try:
        retrieve_response = requests.head(f'http://{server}/retrieve/{filename}/{chunk_id}')
        return retrieve_response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@app.route('/files/<filename>', methods=['DELETE'])
def delete(filename):
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

                if delete_response.status_code != 200:
                    return jsonify({"error": f'Error deleting file chunk {chunk_id} from chunk server {server}'}), 500
            except requests.exceptions.RequestException:
                return jsonify({"error": f'Error deleting file chunk {chunk_id} from chunk server {server}'}), 500

    # Delete file from master server
    delete_master_response = requests.delete(f'{config.MASTER_URL}/v1/files/{filename}')
    if delete_master_response.status_code != 200:
        return jsonify({"error": f"Error deleting file from master server: {delete_master_response.json()['error']}"}), 500

    return jsonify({'message': 'Filed deleted succesfully'}), 200


@app.route('/files/<filename>/size', methods=['GET'])
def size(filename):
    size_response = requests.get(f'{config.MASTER_URL}/v1/files/{filename}/size')
    return size_response.json(), size_response.status_code


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'message': 'healthy'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
