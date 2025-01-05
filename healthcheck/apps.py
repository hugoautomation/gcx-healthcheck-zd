from django.apps import AppConfig
import segment.analytics as analytics
from zendeskapp import settings
import logging

logger = logging.getLogger(__name__)


class HealthcheckConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "healthcheck"

    def ready(self):
        # Configure Segment analytics
        analytics.write_key = settings.SEGMENT_WRITE_KEY

        # Import signal handlers
        try:
            # Import the views module where webhook handlers are defined
            from healthcheck import views  # noqa

            logger.info("Successfully loaded webhook handlers")
        except ImportError as e:
            logger.error(f"Failed to load webhook handlers: {str(e)}")
            pass
