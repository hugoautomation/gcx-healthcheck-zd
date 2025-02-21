from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from zendeskapp import settings
from ..models import ZendeskUser, SiteConfiguration
from ..utils.formatting import format_historical_reports
from ..utils.stripe import get_default_subscription_status
import segment.analytics as analytics  # Add this import
from ..cache_utils import HealthCheckCache
import jwt
from functools import wraps


# Add this new decorator to validate JWT tokens
def validate_jwt_token(f):
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        # Only validate JWT for initial page loads (POST requests)
        if request.method == "POST" and not request.headers.get("X-Subsequent-Request"):
            try:
                # Get token based on content type
                if request.content_type == "application/json":
                    try:
                        data = json.loads(request.body)
                        token = data.get("token")
                    except json.JSONDecodeError:
                        token = None
                else:
                    # Handle form data
                    token = request.POST.get("token")

                if not token:
                    return JsonResponse({"error": "No token provided"}, status=403)

                # Validate token
                try:
                    decoded_token = jwt.decode(
                        token, options={"verify_signature": False}
                    )
                    request.zendesk_jwt = decoded_token
                    request.subdomain = decoded_token.get("iss", "").replace(
                        ".zendesk.com", ""
                    )
                except Exception as e:
                    return JsonResponse(
                        {"error": f"Invalid token format: {str(e)}"}, status=403
                    )

            except Exception as e:
                return JsonResponse({"error": str(e)}, status=403)

        return f(request, *args, **kwargs)

    return decorated_function


# Update the app view to remove monitoring context
@csrf_exempt
@validate_jwt_token
def app(request):
    initial_data = {}
    installation_id = request.GET.get("installation_id")
    app_guid = request.GET.get("app_guid")
    origin = request.GET.get("origin")
    user_id = request.GET.get("user_id")

    if not all([installation_id, user_id]):
        initial_data["loading"] = "Loading your workspace..."
        return render(request, "healthcheck/app.html", initial_data)

    try:
        # Get all cached data in parallel
        # Initialize subscription_status with default values
        subscription_status = get_default_subscription_status()

        # url_params = HealthCheckCache.get_url_params(installation_id, app_guid, origin, user_id)
        user = HealthCheckCache.get_user_info(user_id)
        if user:
            # Only try to get subscription status if we have a user
            subscription_status = HealthCheckCache.get_subscription_status(
                user.subdomain
            )

        latest_report = HealthCheckCache.get_latest_report(installation_id)
        historical_reports = HealthCheckCache.get_historical_reports(installation_id)
        monitoring_settings = HealthCheckCache.get_monitoring_settings(installation_id)

        # Identify user with Segment
        analytics.identify(
            user_id,
            {
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "locale": user.locale,
                "timezone": user.time_zone,
                "avatar": user.avatar_url,
                "subdomain": user.subdomain,
                "subscription_status": subscription_status["status"],
                "subscription_plan": subscription_status["plan"],
                "subscription_active": subscription_status["active"],
                "installation_id": installation_id,
                "last_healthcheck": latest_report.created_at if latest_report else None,
                "last_healthcheck_unlocked": latest_report.is_unlocked
                if latest_report
                else False,
            },
        )

        # Group analytics
        analytics.group(
            user_id,
            user.subdomain,
            {
                "name": user.subdomain,
                "organization": user.subdomain,
                "subscription_status": subscription_status["status"],
            },
        )

        # Track app load
        analytics.track(
            user_id,
            "App Loaded",
            {
                "subscription_status": subscription_status["status"],
                "subscription_active": subscription_status["active"],
                "subdomain": origin,
                "installation_id": installation_id,
            },
        )

        if latest_report:
            # Use cached formatted report data
            report_data = HealthCheckCache.get_formatted_report(
                latest_report, subscription_status["active"]
            )

            initial_data.update(
                {
                    "historical_reports": format_historical_reports(historical_reports),
                    "data": report_data,
                    "monitoring": monitoring_settings,
                }
            )
        else:
            initial_data.update(
                {
                    "warning": "No health check reports found. Please run your first health check.",
                    "historical_reports": [],
                    "data": None,
                }
            )

    except Exception as e:
        print(f"Error in app view: {str(e)}")
        initial_data["error"] = f"Error loading health check data: {str(e)}"

    # Prepare context for template
    initial_data.update(
        {
            "url_params": {
                "installation_id": installation_id,
                "app_guid": app_guid,
                "origin": origin,
                "user_id": user_id,
            },
            "subscription": {
                "is_active": subscription_status["active"],
                "status": subscription_status["status"],
                "current_period_end": subscription_status.get("current_period_end"),
                "plan": subscription_status.get("plan"),
            },
            "environment": settings.ENVIRONMENT,
            "site_config": SiteConfiguration.objects.first(),
        }
    )

    return render(request, "healthcheck/app.html", initial_data)


@csrf_exempt
@require_http_methods(["POST"])
def create_or_update_user(request):
    """Handle user creation/update from Zendesk app"""
    try:
        # Log incoming request for debugging
        print("Request Headers:", request.headers)
        print("Request Body:", request.body.decode("utf-8"))

        # Parse and validate data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", str(e))
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON data"}, status=400
            )

        # Convert user_id to integer since model expects BigIntegerField
        try:
            user_id = int(data.get("user_id"))
        except (TypeError, ValueError) as e:
            print("Error converting user_id:", str(e))
            return JsonResponse(
                {"status": "error", "message": "Invalid user_id format"}, status=400
            )

        # Required fields based on model definition
        required_fields = ["user_id", "name", "email", "role", "locale", "subdomain"]
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            print("Validation Error:", error_msg)
            return JsonResponse({"status": "error", "message": error_msg}, status=400)

        # Create or update user with exact model field mapping
        try:
            user, created = ZendeskUser.objects.update_or_create(
                user_id=user_id,
                defaults={
                    "name": data["name"],
                    "email": data["email"],
                    "role": data["role"],
                    "locale": data["locale"],
                    "subdomain": data["subdomain"],
                    "time_zone": data.get("time_zone"),
                    "avatar_url": data.get("avatar_url"),
                    "plan": data.get("plan"),
                },
            )

            return JsonResponse(
                {"status": "success", "user_id": user.user_id, "created": created}
            )

        except Exception as e:
            print("Database Error:", str(e))
            return JsonResponse(
                {"status": "error", "message": f"Database error: {str(e)}"}, status=400
            )

    except Exception as e:
        print("Unexpected Error:", str(e))
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
