#!/bin/bash
# Start Celery workers
celery -A zendeskapp worker --loglevel=info --concurrency=8 &

# Start Django
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn zendeskapp.wsgi