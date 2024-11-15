from flask import Flask
import os
from dotenv import load_dotenv
# Load environment variables first
load_dotenv()

app = Flask(__name__)

# Configuration
app.config.update(
    DB_NAME=os.getenv('PGDATABASE'),
    DB_USER=os.getenv('PGUSER'),
    DB_PASSWORD=os.getenv('PGPASSWORD'),
    DB_HOST=os.getenv('PGHOST'),
    DB_PORT=os.getenv('PGPORT'),
    REDIS_URL=os.getenv('REDIS_URL') or 'redis://default:pXsTxkPHpoSDnCEBpgTGKsdQKZxzYcuA@redis.railway.internal:6379'
)

from application import routes