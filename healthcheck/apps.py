from django.apps import AppConfig
import segment.analytics as analytics
from zendeskapp import settings


class HealthcheckConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "healthcheck"

    def ready(self):
        # Configure Segment analytics
        analytics.write_key = settings.SEGMENT_WRITE_KEY

        # Import signal handlers
        try:
            import healthcheck.signals  # noqa
        except ImportError:
            pass
