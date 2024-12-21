# Create your models here.
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from django.core.validators import EmailValidator
from djstripe.models import Subscription


class HealthCheckReport(models.Model):
    """Stores health check reports with raw response data"""

    # Zendesk instance identifiers
    instance_guid = models.CharField(max_length=320, db_index=True)
    installation_id = models.BigIntegerField()
    app_guid = models.CharField(max_length=320)
    subdomain = models.CharField(max_length=255)
    admin_email = models.EmailField(
        null=True, blank=True, help_text="Admin email for API authentication"
    )
    api_token = models.CharField(
        max_length=550, null=True, blank=True, help_text="API token for authentication"
    )

    # App metadata
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
    def has_active_subscription(self):
        """Check if this installation has an active subscription"""
        status = ZendeskUser.get_subscription_status(self.subdomain)
        return status["active"]

    @classmethod
    def update_latest_report_plan(cls, installation_id, new_plan):
        """Update the plan for the latest report of an installation"""
        latest_report = cls.get_latest_for_installation(installation_id)
        if latest_report:
            latest_report.plan = new_plan
            latest_report.save()

            # Check subscription status
            subscription_status = ZendeskUser.get_subscription_status(
                latest_report.subdomain
            )
            if subscription_status["active"]:
                # Update all reports for this installation based on the subscription
                cls.update_all_reports_unlock_status(installation_id, new_plan)

    @classmethod
    def update_all_reports_unlock_status(cls, installation_id, subscription_active):
        """Update unlock status for all reports of an installation based on subscription status"""
        cls.objects.filter(installation_id=installation_id).update(
            is_unlocked=subscription_active
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
            models.Index(
                fields=["subdomain", "created_at"]
            ),  # Add this for subscription queries
        ]

    def save(self, *args, **kwargs):
        # Get subscription status for this installation's subdomain
        subscription_status = ZendeskUser.get_subscription_status(self.subdomain)

        # Auto-unlock if subscription is active
        if subscription_status["active"]:
            self.is_unlocked = True
            # Update all other reports for this installation
            if not kwargs.pop(
                "skip_others", False
            ):  # Add skip flag to prevent recursion
                self.__class__.update_all_reports_unlock_status(
                    self.installation_id, subscription_status["active"]
                )

        super().save(*args, **kwargs)


class HealthCheckMonitoring(models.Model):
    """Manages automated health check monitoring settings"""

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]

    # Link to installation
    installation_id = models.BigIntegerField(unique=True)
    instance_guid = models.CharField(max_length=320)
    subdomain = models.CharField(max_length=255)

    # Monitoring settings
    is_active = models.BooleanField(default=True)
    frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES, default="weekly"
    )
    notification_emails = ArrayField(
        models.EmailField(validators=[EmailValidator()]),
        blank=True,
        help_text="List of email addresses to receive reports",
    )

    # Metadata
    last_check = models.DateTimeField(null=True, blank=True)
    next_check = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def schedule_next_check(self):
        """Calculate and set the next check date based on frequency"""
        if not self.last_check:
            self.last_check = timezone.now()

        if self.frequency == "daily":
            self.next_check = self.last_check + timedelta(days=1)
        elif self.frequency == "weekly":
            self.next_check = self.last_check + timedelta(weeks=1)
        else:  # monthly
            self.next_check = self.last_check + relativedelta(months=1)

    def save(self, *args, **kwargs):
        if not self.next_check:
            self.schedule_next_check()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["installation_id"]),
            models.Index(fields=["next_check"]),
        ]


class ZendeskUser(models.Model):
    """Stores Zendesk user information"""

    user_id = models.BigIntegerField(unique=True)  # Zendesk user ID
    name = models.CharField(max_length=255)
    email = models.EmailField()
    role = models.CharField(max_length=100)
    locale = models.CharField(max_length=50)
    time_zone = models.CharField(max_length=100, null=True, blank=True)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)
    subdomain = models.CharField(max_length=255)
    plan = models.CharField(max_length=320, null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def create_or_update(cls, user_data):
        """Create or update user from Zendesk data"""
        user, _ = cls.objects.update_or_create(
            user_id=user_data["id"],
            defaults={
                "name": user_data["name"],
                "email": user_data["email"],
                "role": user_data["role"],
                "locale": user_data["locale"],
                "time_zone": user_data.get("timeZone", {}).get("ianaName"),
                "avatar_url": user_data.get("avatarUrl"),
                "subdomain": user_data["subdomain"],
            },
        )
        return user

    @classmethod
    def get_subscription_status(cls, subdomain):
        """Get subscription status for a subdomain"""
        try:
            # Look up subscription by metadata and include plan details
            subscription = (
                Subscription.objects.filter(
                    metadata__subdomain=subdomain,
                    status__in=[
                        "active",
                        "trialing",
                    ],  # Include trials if you support them
                )
                .select_related("plan")
                .latest("created")
            )

            return {
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "plan": subscription.plan.nickname if subscription.plan else None,
                "active": subscription.status in ["active", "trialing"],
                "subscription_id": subscription.id,
            }
        except Subscription.DoesNotExist:
            return {
                "status": "no_subscription",
                "active": False,
                "plan": "Free",
                "current_period_end": None,
                "subscription_id": None,
            }

    class Meta:
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["email"]),
        ]
