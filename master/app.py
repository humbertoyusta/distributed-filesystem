import threading
from flask import Flask
from services.health_check_service import health_check
import config

app = Flask(__name__)

rc = config.get_redis()

for i in range(1, int(config.CHUNK_SERVER_NUMBER) + 1):
    rc.sadd('chunk_servers', i)


if __name__ == '__main__':
    threading.Thread(target=health_check).start()
    app.run(host='0.0.0.0', port=5000, debug=True)