from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json
from zendeskapp import settings
from ..models import HealthCheckMonitoring, ZendeskUser
from ..utils.monitoring import get_monitoring_context
from ..utils.stripe import get_default_subscription_status

from ..cache_utils import HealthCheckCache
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def monitoring(request):
    installation_id = request.GET.get("installation_id")
    user_id = request.GET.get("user_id")
    subscription_status = get_default_subscription_status()

    try:
        user = ZendeskUser.objects.get(user_id=user_id)
        if user:
            subscription_status = HealthCheckCache.get_subscription_status(
                user.subdomain
            )

        monitoring_settings = HealthCheckCache.get_monitoring_settings(installation_id)

        if not subscription_status["active"]:
            messages.error(request, "Monitoring requires an active subscription")
            return HttpResponseRedirect(f"/app/?installation_id={installation_id}")

    except Exception as e:
        logger.error(f"Error in monitoring view: {str(e)}")
        return HttpResponseRedirect("/")

    # Validate installation_id
    try:
        if not installation_id or installation_id.lower() == "none":
            messages.error(request, "Installation ID required")
            return HttpResponseRedirect("/")

        # Convert to integer
        installation_id = int(installation_id)
    except (ValueError, TypeError):
        messages.error(request, "Invalid Installation ID")
        return HttpResponseRedirect("/")

    # Get monitoring context
    try:
        context = get_monitoring_context(
            installation_id, subscription_status["active"], None
        )
    except HealthCheckMonitoring.DoesNotExist:
        # Handle case where monitoring settings don't exist yet
        context = {
            "monitoring_settings": monitoring_settings
            or {
                "is_active": False,
                "frequency": "weekly",
                "notification_emails": [],
            },
        }

    # Add URL parameters and environment to context
    context.update(
        {
            "url_params": HealthCheckCache.get_url_params(
                installation_id,
                request.GET.get("app_guid"),
                request.GET.get("origin"),
                user_id,
            ),
            "environment": settings.ENVIRONMENT,
        }
    )

    return render(request, "healthcheck/monitoring.html", context)


@csrf_exempt
def monitoring_settings(request):
    """Handle monitoring settings updates"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        installation_id = data.get("installation_id")
        user_id = data.get("user_id")
        is_active = data.get("is_active", False)
        frequency = data.get("frequency", "weekly")
        notification_emails = data.get("notification_emails", [])

        logger.info(f"Received monitoring settings update: {data}")

        # Validate required fields
        if not installation_id:
            return JsonResponse({"error": "Installation ID required"}, status=400)
        if not user_id:
            return JsonResponse({"error": "User ID required"}, status=400)

        # Get user info for subdomain
        try:
            user = ZendeskUser.objects.get(user_id=user_id)
            subdomain = user.subdomain
        except ZendeskUser.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=400)

        # Get or create monitoring settings
        monitoring, created = HealthCheckMonitoring.objects.update_or_create(
            installation_id=installation_id,
            defaults={
                "is_active": is_active,
                "frequency": frequency,
                "notification_emails": notification_emails or [],
                "subdomain": subdomain,  # Add subdomain
                "instance_guid": data.get(
                    "instance_guid", ""
                ),  # Add instance_guid if available
            },
        )

        # Invalidate cache
        HealthCheckCache.invalidate_monitoring_settings(installation_id)

        logger.info(
            f"Successfully updated monitoring settings for installation {installation_id}"
        )

        return JsonResponse(
            {
                "status": "success",
                "message": "Settings saved successfully",
                "data": {
                    "is_active": monitoring.is_active,
                    "frequency": monitoring.frequency,
                    "notification_emails": monitoring.notification_emails or [],
                },
            }
        )

    except Exception as e:
        logger.error(f"Error saving monitoring settings: {str(e)}", exc_info=True)
        return JsonResponse(
            {"error": "Failed to save monitoring settings", "details": str(e)},
            status=500,
        )
