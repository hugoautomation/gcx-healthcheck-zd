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
    updated_at = models.DateTimeField(auto_now=True)

    # Payment status
    is_unlocked = models.BooleanField(default=False)  # New field
    stripe_payment_id = models.CharField(
        max_length=320, null=True, blank=True
    )  # Optional: track payment ID

    @classmethod
    def get_latest_for_installation(cls, installation_id):
        """Get the most recent report for an installation"""
        return (
            cls.objects.filter(installation_id=installation_id)
            .order_by("-created_at")
            .first()
        )

    @property
    def is_latest(self):
        """Check if this is the latest report for the installation"""
        latest = self.__class__.get_latest_for_installation(self.installation_id)
        return latest and latest.id == self.id

    @property
    def previous_report(self):
        """Get the previous report for this installation"""
        return (
            self.__class__.objects.filter(
                installation_id=self.installation_id, created_at__lt=self.created_at
            )
            .order_by("-created_at")
            .first()
        )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["instance_guid", "created_at"]),
            models.Index(fields=["installation_id", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        # Auto-unlock for non-Free plans
        if self.plan != "Free":
            self.is_unlocked = True
        super().save(*args, **kwargs)
