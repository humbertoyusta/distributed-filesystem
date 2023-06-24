from flask import Flask, redirect
from threading import Thread
from time import sleep
import requests
import os

app = Flask(__name__)

# Number of services to load balance
num_services = int(os.getenv("NUMBER_OF_SERVICES", 1))

# Define the base name of your services
base_service_name = 'client_'

# List of your backend servers
internal_services = [f"http://{base_service_name}{i}:5000" for i in range(1, num_services + 1)]
external_services = [f"http://localhost:{5001 + i}" for i in range(1, num_services + 1)]
healthy_services = list(zip(internal_services, external_services))


def health_check():
    global healthy_services
    while True:
        for internal_service, external_service in zip(internal_services, external_services):
            try:
                response = requests.get(f'{internal_service}/health', timeout=2)
                if response.status_code == 200:
                    if (internal_service, external_service) not in healthy_services:
                        healthy_services.append((internal_service, external_service))
                else:
                    if (internal_service, external_service) in healthy_services:
                        healthy_services.remove((internal_service, external_service))
            except requests.exceptions.RequestException:
                if (internal_service, external_service) in healthy_services:
                    healthy_services.remove((internal_service, external_service))
        sleep(10)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def load_balancer(path):
    if not healthy_services:
        return 'No healthy services', 503
    # Round-robin load balancing by rotating the list of healthy backends
    internal_service, external_service = healthy_services.pop(0)
    healthy_services.append((internal_service, external_service))

    print(f'Load balancing request to {internal_service}/{path}')
    return redirect(f'{external_service}/{path}', 307)


if __name__ == "__main__":
    # Start the service discovery and health check threads
    Thread(target=health_check).start()
    app.run(port=5000, host="0.0.0.0", debug=True)
