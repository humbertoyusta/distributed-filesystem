import threading
from flask import Flask, Blueprint
from controllers.files_controller import files_blueprint
from services.health_check_service import health_check
import config
from services.replication_service import replication

# Create the Flask app and Redis client
app = Flask(__name__)
rc = config.get_redis()

# Add all chunk servers to the set of chunk servers in Redis
for i in range(1, int(config.CHUNK_SERVER_NUMBER) + 1):
    rc.sadd('chunk_servers', i)

# define the v1 blueprint
v1 = Blueprint('v1', __name__)
v1.register_blueprint(files_blueprint, url_prefix='/files')
app.register_blueprint(v1, url_prefix='/v1')

if __name__ == '__main__':
    threading.Thread(target=health_check).start()
    threading.Thread(target=replication).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
