from zendeskapp import settings
from djstripe.models import WebhookEndpoint


def get_default_subscription_status():
    """Helper function to return default subscription status"""
    return {
        "status": "inactive",
        "active": False,
        "plan": "Free",
        "current_period_end": None,
        "subscription_id": None,
    }


def create_webhook_endpoint(request):
    """Create or get a webhook endpoint"""
    webhook_url = request.build_absolute_uri("/stripe/webhook/")

    # Try to get existing webhook or create new one
    webhook_endpoint = WebhookEndpoint.objects.filter(url=webhook_url).first()
    if not webhook_endpoint:
        webhook_endpoint = WebhookEndpoint.objects.create(
            url=webhook_url,
            secret=settings.DJSTRIPE_WEBHOOK_SECRET,
            active=True,
            # api_version=settings.STRIPE_API_VERSION,
        )

    return webhook_endpoint
