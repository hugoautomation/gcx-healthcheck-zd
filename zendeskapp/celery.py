import os


from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zendeskapp.settings")

app = Celery("zendeskapp")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.update(
    worker_max_tasks_per_child=50,  # Restart workers after 50 tasks
    worker_prefetch_multiplier=1,    # Don't prefetch tasks
    worker_timeout=900,              # 15 minutes timeout
    task_time_limit=900,            # 15 minutes hard timeout
    task_soft_time_limit=600,       # 10 minutes soft timeout
    broker_connection_retry_on_startup=True,
)
# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
