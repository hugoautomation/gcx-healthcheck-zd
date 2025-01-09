from ..models import HealthCheckMonitoring


def get_monitoring_context(installation_id, subscription_active, latest_report=None):
    """Helper function to get monitoring settings context"""
    try:
        monitoring = HealthCheckMonitoring.objects.get(installation_id=installation_id)

        # First check if subscription is active, if not, monitoring should be disabled
        if not subscription_active:
            monitoring_data = {
                "is_active": False,  # Force inactive if no subscription
                "frequency": monitoring.frequency,
                "notification_emails": monitoring.notification_emails or [],
                "instance_guid": monitoring.instance_guid,
                "subdomain": monitoring.subdomain,
            }
        else:
            monitoring_data = {
                "is_active": monitoring.is_active,  # Only use monitoring setting if subscription is active
                "frequency": monitoring.frequency,
                "notification_emails": monitoring.notification_emails or [],
                "instance_guid": monitoring.instance_guid,
                "subdomain": monitoring.subdomain,
            }

    except HealthCheckMonitoring.DoesNotExist:
        monitoring_data = {
            "is_active": False,
            "frequency": "weekly",
            "notification_emails": [],
            "instance_guid": latest_report.instance_guid if latest_report else "",
            "subdomain": latest_report.subdomain if latest_report else "",
        }

    return {
        "monitoring_settings": monitoring_data,
        "subscription_active": subscription_active,
    }
