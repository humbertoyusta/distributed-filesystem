import os

MASTER_URL = os.getenv('MASTER_URL')
CHUNK_SIZE = os.getenv('CHUNK_SIZE') if os.getenv('CHUNK_SIZE') else 1024 # 1KB
