#!/bin/bash
# Start Celery workers
celery -A zendeskapp worker --loglevel=info --concurrency=8 &

# Start Django
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn zendeskapp.wsgi:application --timeout 120 --workers 2 --threads 2 --keep-alive 120 --max-requests-jitter 50 --max-requests 1000 --worker-class gthread