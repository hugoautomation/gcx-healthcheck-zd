from celery import shared_task
from .models import HealthCheckReport
import requests
import logging
from django.conf import settings
logger = logging.getLogger(__name__)
@shared_task
def run_health_check(url, email, api_token, installation_id, user_id, subdomain, instance_guid, app_guid, stripe_subscription_id, version):
    try:
        # Construct proper Zendesk URL
        zendesk_url = f"https://{subdomain}.zendesk.com"
        
        api_url = (
            "https://app.configly.io/api/health-check/"
            if settings.ENVIRONMENT == "production"
            else "https://django-server-development-1b87.up.railway.app/api/health-check/"
        )

        # Make API request
        response = requests.post(
            api_url,
            headers={
                "X-API-Token": settings.HEALTHCHECK_TOKEN,
                "Content-Type": "application/json",
            },
            json={
                "url": zendesk_url,  # Use the properly constructed URL
                "email": email,
                "api_token": api_token,
                "status": "active",
            },
        )

        if response.status_code != 200:
            error_message = "Authentication failed." if response.status_code == 401 else f"API Error: {response.text}"
            return {"error": True, "message": error_message}

        response_data = response.json()

        # Create report
        report = HealthCheckReport.objects.create(
            installation_id=installation_id,
            api_token=api_token,
            admin_email=email,
            instance_guid=instance_guid,
            subdomain=subdomain,
            app_guid=app_guid,
            stripe_subscription_id=stripe_subscription_id,
            version=version,
            raw_response=response_data,
        )

        return {"error": False, "report_id": report.id}

    except Exception as e:
        logger.error(f"Health check task error: {str(e)}")
        return {"error": True, "message": str(e)}