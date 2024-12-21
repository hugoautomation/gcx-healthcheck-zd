# Register your models here.
from django.contrib import admin
from .models import HealthCheckReport, HealthCheckMonitoring, ZendeskUser


@admin.register(HealthCheckReport)
class HealthCheckReportAdmin(admin.ModelAdmin):
    list_display = ("installation_id", "subdomain", "is_unlocked", "created_at")
    list_filter = ("is_unlocked", "created_at", "updated_at")
    search_fields = ("installation_id", "subdomain", "instance_guid", "admin_email")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Instance Information",
            {
                "fields": (
                    "instance_guid",
                    "installation_id",
                    "app_guid",
                    "subdomain",
                    "admin_email",
                )
            },
        ),
        ("Plan Information", {"fields": ("stripe_subscription_id", "version")}),
        ("Report Status", {"fields": ("is_unlocked", "stripe_payment_id")}),
        ("Report Data", {"fields": ("raw_response",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(HealthCheckMonitoring)
class HealthCheckMonitoringAdmin(admin.ModelAdmin):
    list_display = (
        "installation_id",
        "subdomain",
        "is_active",
        "frequency",
        "last_check",
        "next_check",
    )
    list_filter = ("is_active", "frequency", "created_at")
    search_fields = (
        "installation_id",
        "subdomain",
        "instance_guid",
        "notification_emails",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Instance Information",
            {"fields": ("installation_id", "instance_guid", "subdomain")},
        ),
        (
            "Monitoring Settings",
            {"fields": ("is_active", "frequency", "notification_emails")},
        ),
        ("Schedule Information", {"fields": ("last_check", "next_check")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(ZendeskUser)
class ZendeskUserAdmin(admin.ModelAdmin):
    list_display = (
        "user_id",
        "name",
        "email",
        "role",
        "subdomain",
    )
