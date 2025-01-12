#!/bin/bash
# Start Celery workers
celery -A zendeskapp worker \
    --loglevel=info \
    --timeout=900 \
    --max-tasks-per-child=50 \
    --concurrency=8 \
    --pool=prefork &

# Start Django
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn zendeskapp.wsgi