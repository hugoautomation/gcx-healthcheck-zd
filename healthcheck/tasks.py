from celery import shared_task
from .models import HealthCheckReport
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    time_limit=120,  # 2 minute timeout
)
def run_health_check(
    self,
    url,
    email,
    api_token,
    installation_id,
    user_id,
    subdomain,
    instance_guid,
    app_guid,
    stripe_subscription_id,
    version,
):
    try:
        zendesk_url = f"https://{subdomain}.zendesk.com"
        api_url = (
            "https://app.configly.io/api/health-check/"
            if settings.ENVIRONMENT == "production"
            else "https://django-server-development-1b87.up.railway.app/api/health-check/"
        )

        logger.info(f"Starting health check for subdomain: {subdomain}")
        logger.info(f"Making request to: {api_url}")

        response = requests.post(
            api_url,
            headers={
                "X-API-Token": settings.HEALTHCHECK_TOKEN,
                "Content-Type": "application/json",
                "User-Agent": f"HealthCheck/v{version}",
            },
            json={
                "url": zendesk_url,
                "email": email,
                "api_token": api_token,
                "status": "active",
            },
            timeout=(30, 300),
        )

        logger.info(f"Response status code: {response.status_code}")
        logger.info(
            f"Response content: {response.text[:500]}"
        )  # Log first 500 chars of response

        if response.status_code == 502:
            attempt = self.request.retries + 1
            logger.warning(
                f"Received 502 error for {subdomain}, attempt {attempt} of 3"
            )

            if attempt < 3:  # Only retry if we haven't hit max retries
                countdown = 60 * (2**self.request.retries)
                logger.info(f"Retrying in {countdown} seconds...")
                self.retry(
                    exc=Exception(f"502 error from API for {subdomain}"),
                    countdown=countdown,
                )
            else:
                logger.error(f"Max retries reached for {subdomain}")
                return {
                    "error": True,
                    "message": "Health check failed after multiple retries. The instance might be too large or temporarily unavailable.",
                }

        # Rest of the status code handling
        if response.status_code == 429:
            logger.warning(f"Rate limit hit for {subdomain}")
            if self.request.retries < 2:
                self.retry(countdown=300)
            return {
                "error": True,
                "message": "Rate limit exceeded. Please try again later.",
            }

        if response.status_code != 200:
            error_message = (
                "Authentication failed."
                if response.status_code == 401
                else f"API Error: {response.text}"
            )
            logger.error(f"API error for {subdomain}: {error_message}")
            return {"error": True, "message": error_message}

        # Success path
        response_data = response.json()
        logger.info(f"Successfully received response for {subdomain}")

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

        logger.info(f"Successfully completed health check for {subdomain}")
        return {"error": False, "report_id": report.id}

    except Exception as e:
        logger.error(
            f"Error during health check for {subdomain}: {str(e)}", exc_info=True
        )
        return {"error": True, "message": f"Health check failed: {str(e)}"}
