from django.apps import AppConfig
import segment.analytics as analytics
from zendeskapp import settings


class HealthcheckConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "healthcheck"

    def ready(self):
        analytics.write_key = settings.SEGMENT_WRITE_KEY
