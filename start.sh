#!/bin/bash
# Start Celery workers
celery -A zendeskapp worker --loglevel=info --concurrency=8 &

# Start Django
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn zendeskapp.wsgi:application --workers 2 --threads 2 --timeout 120 --max-requests-jitter 50 --worker-class gthread