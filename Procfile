web: gunicorn --worker-class gthread --threads 4 --timeout 120 -w 1 --bind 0.0.0.0:$PORT app:app
release: flask --app app init-db
