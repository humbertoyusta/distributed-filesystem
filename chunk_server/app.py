from flask import Flask, request, send_file, jsonify
import config
import os

app = Flask(__name__)
rc = config.get_redis()


@app.route('/store/<filename>/<int:chunk_id>', methods=['POST'])
def store_chunk(filename: str, chunk_id: int):
    """Store a chunk of a file on the chunk server and updates the chunk server information
    in Redis telling that the chunk is available on this chunk server.
    :param filename: The name of the file
    :param chunk_id: The ID of the chunk in the file
    :return: A JSON response with a message if the file was stored successfully"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    file = request.files['file']
    filename_without_ext, ext = os.path.splitext(filename)
    chunkname = f"{filename_without_ext}_{chunk_id}{ext}"
    file.save(os.path.join(config.UPLOAD_FOLDER, chunkname))

    # Update chunk server information in Redis
    chunk_server_info = f"{config.CHUNK_SERVER_BASE_NAME}{config.CHUNK_SERVER_ID}:{config.CHUNK_SERVER_PORT}"
    redis_key = f'file:{filename}:chunks:{chunk_id}:chunk_servers'
    rc.sadd(redis_key, chunk_server_info)

    return jsonify({'message': 'File stored successfully'}), 200


@app.route('/retrieve/<filename>/<int:chunk_id>', methods=['GET', 'HEAD'])
def retrieve_chunk(filename: str, chunk_id: int):
    """Retrieve a chunk of a file from the chunk server.
    :param filename: The name of the file
    :param chunk_id: The ID of the chunk in the file
    :return: the requested chunk or a 404 if the chunk does not exist"""
    try:
        filename_without_ext, ext = os.path.splitext(filename)
        chunk_name = f"{filename_without_ext}_{chunk_id}{ext}"
        if request.method == 'HEAD':
            if os.path.exists(os.path.join(config.UPLOAD_FOLDER, chunk_name)):
                return jsonify({'message': 'File exists'}), 200
            else:
                return jsonify({'error': 'File not found'}), 404
        elif request.method == 'GET':
            return send_file(os.path.join(config.UPLOAD_FOLDER, chunk_name))
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404


@app.route('/delete/<filename>/<int:chunk_id>', methods=['DELETE'])
def delete_chunk(filename: str, chunk_id: int):
    """Delete a chunk of a file from the chunk server and updates the chunk server information
    in Redis telling that the chunk is no longer available on this chunk server.
    :param filename: The name of the file
    :param chunk_id: The ID of the chunk in the file
    :return: A JSON response with a message if the file was deleted successfully"""
    filename_without_ext, ext = os.path.splitext(filename)
    chunk_name = f"{filename_without_ext}_{chunk_id}{ext}"
    file_path = os.path.join(config.UPLOAD_FOLDER, chunk_name)
    try:
        # Delete file from disk
        os.remove(file_path)

        # Update chunk server information in Redis
        chunk_server_info = f"{config.CHUNK_SERVER_BASE_NAME}{config.CHUNK_SERVER_ID}:{config.CHUNK_SERVER_PORT}"
        redis_key = f'file:{filename}:chunks:{chunk_id}:chunk_servers'
        rc.srem(redis_key, 0, chunk_server_info)

        return jsonify({'message': 'File deleted successfully'}), 200
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint
    :return: A JSON response with a message if the chunk server is healthy"""
    return jsonify({'message': 'healthy'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
