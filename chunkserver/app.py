from flask import Flask, request, send_file
import os

app = Flask(__name__)

# Configure the path where you want to store your chunks
app.config['UPLOAD_FOLDER'] = '/chunks'


@app.route('/store/<chunkname>', methods=['POST'])
def store_chunk(chunkname):
    if 'file' not in request.files:
        return 'No file part', 400

    file = request.files['file']
    filename = chunkname
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    return 'File stored successfully', 200


@app.route('/retrieve/<chunkname>', methods=['GET'])
def retrieve_chunk(chunkname):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], chunkname))


@app.route('/delete/<chunkname>', methods=['DELETE'])
def delete_chunk(chunkname):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], chunkname)
    try:
        os.remove(file_path)
        return 'File deleted successfully', 200
    except:
        return 'File not found', 404


@app.route('/size/<chunkname>', methods=['GET'])
def size_chunk(chunkname):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], chunkname)
    try:
        size = os.path.getsize(file_path)
        return str(size), 200
    except:
        return 'File not found', 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
