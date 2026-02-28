import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    
    # MongoDB Configuration
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/'
    DATABASE_NAME = 'health_recipe_modifier'
    
    # MongoDB Connection Pool Configuration
    # Maximum number of connections in the pool (increased for better concurrency)
    MONGODB_MAX_POOL_SIZE = int(os.environ.get('MONGODB_MAX_POOL_SIZE', 100))
    
    # Minimum number of connections to maintain in the pool (warm pool for faster access)
    MONGODB_MIN_POOL_SIZE = int(os.environ.get('MONGODB_MIN_POOL_SIZE', 20))
    
    # Maximum time (ms) a connection can remain idle before being removed
    MONGODB_MAX_IDLE_TIME_MS = int(os.environ.get('MONGODB_MAX_IDLE_TIME_MS', 45000))  # 45 seconds
    
    # Maximum time (ms) to wait for a connection from the pool
    MONGODB_WAIT_QUEUE_TIMEOUT_MS = int(os.environ.get('MONGODB_WAIT_QUEUE_TIMEOUT_MS', 5000))  # 5 seconds
    
    # Server selection timeout (ms) - how long to wait for server selection
    MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(os.environ.get('MONGODB_SERVER_SELECTION_TIMEOUT_MS', 10000))  # 10 seconds
    
    # Connection timeout (ms) - how long to wait for initial connection
    MONGODB_CONNECT_TIMEOUT_MS = int(os.environ.get('MONGODB_CONNECT_TIMEOUT_MS', 10000))  # 10 seconds
    
    # Socket timeout (ms) - how long to wait for socket operations
    MONGODB_SOCKET_TIMEOUT_MS = int(os.environ.get('MONGODB_SOCKET_TIMEOUT_MS', 20000))  # 20 seconds
    
    # Maximum number of milliseconds that a connection can be in the pool before being removed and replaced
    MONGODB_MAX_CONNECTING = int(os.environ.get('MONGODB_MAX_CONNECTING', 2))  # Limit concurrent connection establishment
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # USDA Nutrition API Configuration
    USDA_API_KEY = os.environ.get('USDA_API_KEY') or ''

