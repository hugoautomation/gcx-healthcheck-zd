# Create your models here.
from django.db import models
from django.utils import timezone


class HealthCheckReport(models.Model):
    """Stores health check reports with raw response data"""

    # Zendesk instance identifiers
    instance_guid = models.CharField(max_length=320, db_index=True)
    installation_id = models.BigIntegerField()
    app_guid = models.CharField(max_length=320)
    subdomain = models.CharField(max_length=255)

    # App metadata
    plan = models.CharField(max_length=320, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=320, null=True, blank=True)
    version = models.CharField(max_length=50)

    # Report data
    raw_response = models.JSONField()  # Store the complete API response
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)  # Add this line

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["instance_guid", "created_at"])]

    def __str__(self):
        return f"Report for {self.subdomain} at {self.created_at}"
