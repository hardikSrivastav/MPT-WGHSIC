release: python -c "from init_db import init_db; init_db()"
web: gunicorn "application:app" --bind 0.0.0.0:$PORT
