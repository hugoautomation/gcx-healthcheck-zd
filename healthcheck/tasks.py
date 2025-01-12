from celery import shared_task
from .models import HealthCheckReport
import requests
import logging
from django.conf import settings
from celery.exceptions import MaxRetriesExceededError
from requests.exceptions import Timeout, ConnectionError, RequestException

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    time_limit=120,          # 2 minute timeout
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
    """
    Run health check task with improved error handling and timeout management.
    
    Args:
        self: Task instance (provided by bind=True)
        url: Zendesk instance URL
        email: Admin email
        api_token: API token
        installation_id: Installation ID
        user_id: User ID
        subdomain: Zendesk subdomain
        instance_guid: Instance GUID
        app_guid: App GUID
        stripe_subscription_id: Stripe subscription ID
        version: App version
    
    Returns:
        dict: Task result with error status and message/report_id
    """
    try:
        # Construct proper Zendesk URL
        zendesk_url = f"https://{subdomain}.zendesk.com"

        # Determine API URL based on environment
        api_url = (
            "https://app.configly.io/api/health-check/"
            if settings.ENVIRONMENT == "production"
            else "https://django-server-development-1b87.up.railway.app/api/health-check/"
        )

        logger.info(f"Starting health check for subdomain: {subdomain}")

        # Make API request with extended timeouts
        response = requests.post(
            api_url,
            headers={
                "X-API-Token": settings.HEALTHCHECK_TOKEN,
                "Content-Type": "application/json",
                "User-Agent": f"HealthCheck/v{version}"
            },
            json={
                "url": zendesk_url,
                "email": email,
                "api_token": api_token,
                "status": "active",
            },
            timeout=(30, 300)  # (connect timeout, read timeout) in seconds
        )

        # Handle different response status codes
        if response.status_code == 502:
            logger.warning(f"Received 502 error for {subdomain}, attempt {self.request.retries + 1}")
            # Retry with exponential backoff: 60s, 120s, 240s
            try:
                raise self.retry(
                    exc=Exception(f"502 error from API for {subdomain}"),
                    countdown=60 * (2 ** self.request.retries)
                )
            except MaxRetriesExceededError:
                return {
                    "error": True,
                    "message": "Health check failed after multiple retries. The instance might be too large or temporarily unavailable."
                }

        if response.status_code == 429:
            logger.warning(f"Rate limit hit for {subdomain}")
            # Retry with longer delay for rate limits
            try:
                raise self.retry(countdown=300)  # 5 minute delay
            except MaxRetriesExceededError:
                return {"error": True, "message": "Rate limit exceeded. Please try again later."}

        if response.status_code != 200:
            error_message = (
                "Authentication failed."
                if response.status_code == 401
                else f"API Error: {response.text}"
            )
            logger.error(f"API error for {subdomain}: {error_message}")
            return {"error": True, "message": error_message}

        # Process successful response
        response_data = response.json()

        # Create health check report
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

    except Timeout as e:
        logger.error(f"Timeout error for {subdomain}: {str(e)}")
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            return {
                "error": True,
                "message": "The health check timed out. This might happen with very large Zendesk instances."
            }

    except ConnectionError as e:
        logger.error(f"Connection error for {subdomain}: {str(e)}")
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            return {"error": True, "message": "Failed to connect to the health check service. Please try again later."}

    except RequestException as e:
        logger.error(f"Request error for {subdomain}: {str(e)}")
        return {"error": True, "message": f"Connection error: {str(e)}"}

    except Exception as e:
        logger.error(f"Unexpected error during health check for {subdomain}: {str(e)}", exc_info=True)
        return {"error": True, "message": "An unexpected error occurred. Please try again later."}