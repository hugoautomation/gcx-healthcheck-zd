from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
import json
import requests
from zendeskapp import settings
from .models import HealthCheckReport, HealthCheckMonitoring, ZendeskUser
from .utils import (
    format_response_data,
    get_monitoring_context,
    format_historical_reports,
    render_report_components,
)
import csv
import jwt
from functools import wraps
import segment.analytics as analytics  # Add this import
from django.core.management import call_command
from django.utils import timezone
import logging
import stripe
import os
from djstripe import webhooks
from django.db import transaction
from djstripe.models import Event, Subscription

stripe.api_key = os.environ.get("STRIPE_TEST_SECRET_KEY", "")

logger = logging.getLogger(__name__)


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


@webhooks.handler("checkout.session.completed")
def handle_checkout_completed(event: Event, **kwargs):
    """Handle successful checkout session completion"""
    try:
        # Log the entire event for debugging
        logger.info(f"Received checkout.session.completed webhook event: {event.id}")
        logger.info(f"Full event data: {event.data}")

        # Get the checkout session
        checkout_session = event.data.get("object", {})

        if not checkout_session:
            logger.error("No checkout session found in event data")
            return HttpResponse(status=400)

        # Log checkout session details
        logger.info(f"Checkout session ID: {checkout_session.get('id')}")
        logger.info(f"Payment status: {checkout_session.get('payment_status')}")

        # Extract and log metadata
        metadata = checkout_session.get("metadata", {})
        logger.info(f"Metadata received: {metadata}")

        report_id = metadata.get("report_id")
        subdomain = metadata.get("subdomain")
        user_id = metadata.get("user_id")

        logger.info(
            f"Extracted data - Report ID: {report_id}, Subdomain: {subdomain}, User ID: {user_id}"
        )

        # Verify payment status
        payment_status = checkout_session.get("payment_status")
        if payment_status != "paid":
            logger.error(f"Unexpected payment status: {payment_status}")
            return HttpResponse(status=400)

        if not all([report_id, subdomain]):
            logger.error("Missing required metadata in checkout session")
            return HttpResponse(status=400)

        # Use transaction to ensure database consistency
        with transaction.atomic():
            try:
                logger.info(
                    f"Attempting to find report with ID: {report_id} and subdomain: {subdomain}"
                )
                report = HealthCheckReport.objects.get(
                    id=report_id, subdomain=subdomain
                )

                logger.info(
                    f"Found report, current unlock status: {report.is_unlocked}"
                )
                report.is_unlocked = True
                report.stripe_payment_id = checkout_session.get("id")
                report.save()  # Removed skip_others=True
                logger.info(
                    f"Successfully updated report {report_id} unlock status to True"
                )

                # Track the successful payment
                def track_payment():
                    logger.info(f"Tracking payment for report {report_id}")
                    analytics.track(
                        user_id,
                        "Report Unlocked",
                        {
                            "report_id": report_id,
                            "payment_id": checkout_session.get("id"),
                            "amount": checkout_session.get("amount_subtotal", 0) / 100,
                            "subdomain": subdomain,
                            "discount_amount": checkout_session.get(
                                "total_details", {}
                            ).get("amount_discount", 0)
                            / 100,
                            "final_amount": checkout_session.get("amount_total", 0)
                            / 100,
                        },
                    )

                transaction.on_commit(track_payment)
                logger.info(f"Successfully processed webhook for report {report_id}")
                return HttpResponse(status=200)

            except HealthCheckReport.DoesNotExist:
                logger.error(f"Report {report_id} not found for subdomain {subdomain}")
                return HttpResponse(status=404)

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=400)


@csrf_exempt
def create_payment_intent(request):
    try:
        data = json.loads(request.body)
        report_id = data.get("report_id")
        installation_id = data.get("installation_id")
        user_id = data.get("user_id")

        if not all([report_id, installation_id, user_id]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        # Get user information
        user = ZendeskUser.objects.get(user_id=user_id)

        # Create Stripe checkout session for one-time payment
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            allow_promotion_codes=True,
            billing_address_collection="required",
            automatic_tax={"enabled": True},
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Health Check Report Unlock",
                        },
                        "unit_amount": 24900,  # $249.00
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "report_id": report_id,
                "installation_id": installation_id,
                "user_id": user_id,
                "subdomain": user.subdomain,
            },
            success_url=request.build_absolute_uri(
                f"/report/{report_id}/?success=true"
            ),
        )

        return JsonResponse({"url": checkout_session.url})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# Update the app view to remove monitoring context
@csrf_exempt
@validate_jwt_token
def app(request):
    initial_data = {}
    installation_id = request.GET.get("installation_id")
    app_guid = request.GET.get("app_guid")
    origin = request.GET.get("origin")
    user_id = request.GET.get("user_id")

    if not installation_id:
        initial_data["loading"] = (
            "Loading your workspace..."  # Changed from error to loading
        )
        return render(request, "healthcheck/app.html", initial_data)

    try:
        user = ZendeskUser.objects.get(user_id=user_id)
        latest_report = HealthCheckReport.get_latest_for_installation(installation_id)
        historical_reports = HealthCheckReport.objects.filter(
            installation_id=installation_id
        ).order_by("-created_at")[:10]
        # Get real subscription status
        subscription_status = subscription_status = ZendeskUser.get_subscription_status(
            user.subdomain
        )

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
            # Format the report data
            report_data = format_response_data(
                latest_report.raw_response,
                subscription_active=subscription_status["active"],  # Changed
                report_id=latest_report.id,
                last_check=latest_report.created_at,
                is_unlocked=latest_report.is_unlocked,  # Added
            )

            initial_data.update(
                {
                    "historical_reports": format_historical_reports(historical_reports),
                    "data": report_data,
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


@csrf_exempt
def health_check(request):
    if request.method == "POST":
        try:
            # Extract data from request
            data = json.loads(request.body) if request.body else {}
            installation_id = data.get("installation_id")
            user_id = data.get("user_id")

            logger.info(
                "Health check details",
                extra={
                    "extra_data": json.dumps(
                        {
                            "installation_id": installation_id,
                            "user_id": user_id,
                            "data": data,
                        }
                    )
                },
            )

            # Get user and subscription status
            user = ZendeskUser.objects.get(user_id=user_id)
            subscription_status = ZendeskUser.get_subscription_status(user.subdomain)

            analytics.track(
                user_id,
                "Health Check Started",
                {
                    "subdomain": data.get("subdomain"),
                    "email": data.get("email"),
                    "subscription_status": subscription_status["status"],
                    "subscription_active": subscription_status["active"],
                },
            )

            # Prepare URL
            url = data.get("url")
            if not url or not url.startswith("https://"):
                url = f"https://{url}"

            api_url = (
                "https://app.configly.io/api/health-check/"
                if settings.ENVIRONMENT == "production"
                else "https://django-server-development-1b87.up.railway.app/api/health-check/"
            )

            # Make API request
            api_payload = {
                "url": url,
                "email": data.get("email"),
                "api_token": data.get("api_token"),
                "status": "active",
            }

            logger.info(
                "Making API request",
                extra={
                    "extra_data": json.dumps(
                        {
                            "api_url": api_url,
                            "subdomain": data.get("subdomain"),
                            "payload": api_payload,
                        }
                    )
                },
            )

            response = requests.post(
                api_url,
                headers={
                    "X-API-Token": settings.HEALTHCHECK_TOKEN,
                    "Content-Type": "application/json",
                },
                json=api_payload,
            )

            if response.status_code == 401:
                error_message = "Authentication failed. Please verify your Admin Email and API Token are correct."
                results_html = render_report_components(
                    {"data": None, "error": error_message}
                )
                return JsonResponse({"error": True, "results_html": results_html})

            if response.status_code != 200:
                results_html = render_report_components(
                    {"data": None, "error": f"API Error: {response.text}"}
                )
                return JsonResponse({"error": True, "results_html": results_html})

            # Get response data
            response_data = response.json()

            # Create report
            report = HealthCheckReport.objects.create(
                installation_id=int(installation_id),
                api_token=data.get("api_token"),
                admin_email=data.get("email"),
                instance_guid=data.get("instance_guid"),
                subdomain=data.get("subdomain", ""),
                app_guid=data.get("app_guid"),
                stripe_subscription_id=subscription_status.get("subscription_id"),
                version=data.get("version", "1.0.0"),
                raw_response=response_data,
            )

            analytics.identify(
                user_id,
                {
                    "email": user.email,
                    "last_healthcheck": report.created_at,
                },
            )

            # Format response data with subscription status
            formatted_data = format_response_data(
                response_data,
                subscription_active=subscription_status["active"],
                report_id=report.id,
                last_check=report.created_at,
                is_unlocked=report.is_unlocked,
            )

            # Render results using utility function
            results_html = render_report_components(formatted_data)

            analytics.track(
                user_id,
                "Health Check Completed",
                {
                    "total_issues": len(response_data.get("issues", [])),
                    "report_id": report.id,
                    "critical_issues": sum(
                        1
                        for issue in response_data.get("issues", [])
                        if issue.get("type") == "error"
                    ),
                    "warning_issues": sum(
                        1
                        for issue in response_data.get("issues", [])
                        if issue.get("type") == "warning"
                    ),
                    "is_unlocked": report.is_unlocked,
                    "subscription_status": subscription_status["status"],
                    "subscription_active": subscription_status["active"],
                },
            )

            return JsonResponse({"error": False, "results_html": results_html})

        except Exception as e:
            results_html = render_report_components(
                {"data": None, "error": f"Error processing request: {str(e)}"}
            )
            return JsonResponse({"error": True, "results_html": results_html})

    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
def monitoring(request):
    installation_id = request.GET.get("installation_id")
    client_plan = request.GET.get("plan", "Free")
    app_guid = request.GET.get("app_guid")
    origin = request.GET.get("origin")
    user_id = request.GET.get("user_id")

    try:
        user = ZendeskUser.objects.get(user_id=user_id)
        subscription_status = ZendeskUser.get_subscription_status(user.subdomain)

        if not subscription_status["active"]:
            messages.error(request, "Monitoring requires an active subscription")
            return HttpResponseRedirect(f"/app/?installation_id={installation_id}")

    except Exception as e:
        print(f"Error in monitoring view: {str(e)}")
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
            "is_free_plan": client_plan == "Free",
            "monitoring_settings": {
                "is_active": False,
                "frequency": "weekly",
                "notification_emails": [],
            },
        }

    # Add URL parameters and environment to context
    context.update(
        {
            "url_params": {
                "installation_id": installation_id,
                "plan": client_plan,
                "app_guid": app_guid,
                "origin": origin,
                "user_id": user_id,
            },
            "environment": settings.ENVIRONMENT,
        }
    )

    return render(request, "healthcheck/monitoring.html", context)


@csrf_exempt
def download_report_csv(request, report_id):
    """Download health check report as CSV"""
    try:
        report = HealthCheckReport.objects.get(id=report_id)

        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="healthcheck_report_{report_id}.csv"'
        )

        # Create CSV writer
        writer = csv.writer(response)

        # Write header row
        writer.writerow(
            ["Type", "Severity", "Object Type", "Description", "Zendesk URL"]
        )

        # Write data rows
        for issue in report.raw_response.get("issues", []):
            writer.writerow(
                [
                    issue.get("item_type", ""),
                    issue.get("type", ""),
                    issue.get("item_type", ""),
                    issue.get("message", ""),
                    issue.get("zendesk_url", ""),
                ]
            )

        return response

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


@csrf_exempt
def check_unlock_status(request):
    report_id = request.GET.get("report_id")
    if not report_id:
        return JsonResponse({"error": "No report ID provided"}, status=400)

    try:
        report = HealthCheckReport.objects.get(id=report_id)
        return JsonResponse({"is_unlocked": report.is_unlocked, "report_id": report.id})
    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


@csrf_exempt
def get_historical_report(request, report_id):
    """Fetch a historical report by ID"""
    try:
        report = HealthCheckReport.objects.get(id=report_id)

        # Get subscription status for the report's subdomain
        subscription_status = ZendeskUser.get_subscription_status(report.subdomain)

        # Format the report data
        report_data = format_response_data(
            report.raw_response,
            subscription_active=subscription_status["active"],
            report_id=report.id,
            last_check=report.created_at,
            is_unlocked=report.is_unlocked,
        )

        # Use render_report_components utility
        results_html = render_report_components(report_data)

        return JsonResponse({"results_html": results_html})

    except HealthCheckReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return JsonResponse({"error": "Report not found"}, status=404)
    except Exception as e:
        logger.error(f"Error fetching historical report: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def monitoring_settings(request):
    """Handle monitoring settings updates"""

    # Handle both JSON and form data for installation_id
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
            installation_id = data.get("installation_id")
            user_id = data.get("user_id")  # Get user_id from JSON
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
    else:
        installation_id = request.POST.get("installation_id")
        user_id = request.POST.get("user_id")  # Get user_id from POST

    if not installation_id:
        error_msg = "Installation ID required"
        if request.content_type == "application/json":
            return JsonResponse({"error": error_msg}, status=400)
        messages.error(request, error_msg)
        return HttpResponseRedirect(request.POST.get("redirect_url", "/"))

    # Get the latest report to check plan status
    latest_report = HealthCheckReport.get_latest_for_installation(installation_id)
    is_free_plan = latest_report.plan == "Free" if latest_report else True

    if request.method == "POST":
        if is_free_plan:
            error_msg = "Monitoring not available for free plan"
            if request.content_type == "application/json":
                return JsonResponse({"error": error_msg}, status=400)
            messages.error(request, error_msg)
            return HttpResponseRedirect(request.POST.get("redirect_url", "/"))

        try:
            # Get data based on content type
            if request.content_type == "application/json":
                is_active = data.get("is_active", False)
                frequency = data.get("frequency", "weekly")
                notification_emails = data.get("notification_emails", [])

            else:
                is_active = request.POST.get("is_active") == "on"
                frequency = request.POST.get("frequency", "weekly")
                notification_emails = request.POST.getlist("notification_emails[]")

            # Filter out empty email fields
            notification_emails = [
                email for email in notification_emails if email and email.strip()
            ]

            print(
                f"Processing settings: active={is_active}, frequency={
                    frequency}, emails={notification_emails}"
            )  # Debug log

            # Update or create monitoring settings
            monitoring, created = HealthCheckMonitoring.objects.update_or_create(
                installation_id=installation_id,
                defaults={
                    "instance_guid": latest_report.instance_guid
                    if latest_report
                    else "",
                    "subdomain": latest_report.subdomain if latest_report else "",
                    "is_active": is_active,
                    "frequency": frequency,
                    "notification_emails": notification_emails,
                },
            )
            if is_active and notification_emails:
                monitoring.next_check = timezone.now()
                monitoring.save()

                # Run the scheduled checks command
                try:
                    call_command("run_scheduled_checks")
                    print(f"Scheduled check triggered for {
                          monitoring.subdomain}")
                except Exception as e:
                    print(f"Error running scheduled check: {str(e)}")

            # Track the event
            analytics.track(
                user_id,
                "Monitoring Settings Updated",
                {
                    "is_active": is_active,
                    "frequency": frequency,
                    "notification_emails_count": len(notification_emails),
                    "subdomain": latest_report.subdomain if latest_report else None,
                    "created": created,
                },
            )

            success_msg = "Settings saved successfully"
            if request.content_type == "application/json":
                return JsonResponse(
                    {
                        "status": "success",
                        "message": success_msg,
                        "data": {
                            "is_active": is_active,
                            "frequency": frequency,
                            "notification_emails": notification_emails,
                        },
                    }
                )

            messages.success(request, success_msg)

        except Exception as e:
            error_msg = f"Error saving settings: {str(e)}"
            print(f"Error: {error_msg}")  # Debug log
            if request.content_type == "application/json":
                return JsonResponse({"error": error_msg}, status=500)
            messages.error(request, error_msg)

        if request.content_type != "application/json":
            return HttpResponseRedirect(request.POST.get("redirect_url", "/"))

    try:
        user = ZendeskUser.objects.get(user_id=user_id)
        subscription_status = ZendeskUser.get_subscription_status(user.subdomain)

        context = get_monitoring_context(
            installation_id,
            subscription_status["active"],  # Changed from plan
            latest_report,
        )
        context["url_params"] = {"installation_id": installation_id, "user_id": user_id}

        return render(request, "healthcheck/monitoring.html", context)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@webhooks.handler("customer.subscription.created")
@webhooks.handler("customer.subscription.updated")
@webhooks.handler("customer.subscription.deleted")
def handle_subscription_update(event: Event, **kwargs):
    """Handle subscription updates from Stripe"""
    try:
        logger.info(f"Received subscription webhook event: {event.type}")
        logger.info(f"Full event data: {event.data}")

        subscription = event.data["object"]
        metadata = subscription.get("metadata", {})

        # Extract metadata
        user_id = metadata.get("user_id")
        subdomain = metadata.get("subdomain")
        installation_id = metadata.get("installation_id")

        if not all([user_id, subdomain]):
            logger.error(
                f"Missing required metadata. user_id: {user_id}, subdomain: {subdomain}"
            )
            return HttpResponse(status=400)

        # Get subscription status
        status = subscription.get("status")
        is_active = status in ["active", "trialing"]
        plan_id = subscription.get("plan", {}).get("id")

        logger.info(
            f"Subscription status for {subdomain}: {status}, is_active: {is_active}"
        )

        try:
            # Verify subdomain exists
            if not ZendeskUser.objects.filter(subdomain=subdomain).exists():
                logger.error(f"User not found for subdomain: {subdomain}")
                return HttpResponse(status=404)

            # Only update reports that haven't been individually unlocked
            affected_reports = HealthCheckReport.objects.filter(
                subdomain=subdomain,  # Only update subscription-based reports
            ).update(is_unlocked=True)

            logger.info(
                f"Updated {affected_reports} subscription-based reports for {subdomain} to is_unlocked={is_active}"
            )

            # Update monitoring settings if subscription is inactive
            if not is_active and installation_id:
                try:
                    monitoring = HealthCheckMonitoring.objects.get(
                        installation_id=installation_id
                    )
                    monitoring.is_active = False
                    monitoring.save()
                    logger.info(
                        f"Updated monitoring status for installation {installation_id}"
                    )
                except HealthCheckMonitoring.DoesNotExist:
                    logger.info(
                        f"No monitoring settings found for installation {installation_id}"
                    )

            # Track the event with additional info about affected reports
            analytics.track(
                user_id,
                "Subscription Status Updated",
                {
                    "event_type": event.type,
                    "subscription_status": status,
                    "subscription_active": is_active,
                    "plan": plan_id,
                    "subdomain": subdomain,
                    "installation_id": installation_id,
                    "affected_reports_count": affected_reports,
                    "individually_unlocked_reports_preserved": True,
                },
            )

            logger.info(
                f"Successfully processed subscription update for subdomain {subdomain}. "
                f"Updated {affected_reports} subscription-based reports. "
                f"Individually unlocked reports were preserved."
            )

            return HttpResponse(status=200)

        except Exception as e:
            logger.error(f"Database error: {str(e)}", exc_info=True)
            return HttpResponse(status=500)

    except Exception as e:
        logger.error(f"Error processing subscription webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=400)

@csrf_exempt
def billing_page(request):
    installation_id = request.GET.get("installation_id")
    user_id = request.GET.get("user_id")
    app_guid = request.GET.get("app_guid")
    origin = request.GET.get("origin")

    if not installation_id:
        return JsonResponse({"error": "Installation ID required"}, status=400)

    try:
        user = ZendeskUser.objects.get(user_id=user_id)
        subscription_status = ZendeskUser.get_subscription_status(user.subdomain)

        # Get detailed subscription information
        try:
            # Get all subscriptions for the subdomain
            subscriptions = Subscription.objects.filter(
                metadata__subdomain=user.subdomain
            )
            logger.info(f"Subscriptions: {subscriptions}")

            # Get active subscription
            active_subscription = subscriptions.filter(
                status__in=["active", "trialing"]
            ).first()
            # Get customer if there's an active subscription
            if active_subscription:
                customer = active_subscription.customer
                latest_invoice = active_subscription.latest_invoice

                subscription_details = {
                    # Basic subscription info
                    "status": active_subscription.status,
                    "current_period_start": active_subscription.current_period_start,
                    "current_period_end": active_subscription.current_period_end,
                    "start_date": active_subscription.start_date,
                    "ended_at": active_subscription.ended_at,
                    "cancel_at": active_subscription.cancel_at,
                    "canceled_at": active_subscription.canceled_at,
                    "trial_start": active_subscription.trial_start,
                    "trial_end": active_subscription.trial_end,

                    # Plan details
                    "plan": {
                        "id": active_subscription.plan.id,
                        "nickname": active_subscription.plan.nickname,
                        "amount": active_subscription.plan.amount,
                        "interval": active_subscription.plan.interval,
                        "product_name": active_subscription.plan.product.name,
                        "currency": active_subscription.plan.currency,
                    },

                    # Customer details
                    "customer": {
                        "name": customer.name,
                        "email": customer.email,
                        "address": customer.address,
                        "currency": customer.currency,
                        "balance": customer.balance,
                        "delinquent": customer.delinquent,
                        "default_payment_method": {
                            "type": customer.default_payment_method.type if customer.default_payment_method else None,
                            "card_brand": customer.default_payment_method.card.brand if customer.default_payment_method and hasattr(customer.default_payment_method, 'card') else None,
                            "card_last4": customer.default_payment_method.card.last4 if customer.default_payment_method and hasattr(customer.default_payment_method, 'card') else None,
                        } if customer.default_payment_method else None,
                    },

                    # Invoice details
                    "latest_invoice": {
                        "number": latest_invoice.number if latest_invoice else None,
                        "amount_due": latest_invoice.amount_due if latest_invoice else None,
                        "amount_paid": latest_invoice.amount_paid if latest_invoice else None,
                        "hosted_invoice_url": latest_invoice.hosted_invoice_url if latest_invoice else None,
                        "pdf_url": latest_invoice.invoice_pdf if latest_invoice else None,
                        "status": latest_invoice.status if latest_invoice else None,
                    } if latest_invoice else None,

                    # Discount information
                    "discount": {
                        "coupon": {
                            "amount_off": customer.coupon.amount_off if customer.coupon else None,
                            "percent_off": customer.coupon.percent_off if customer.coupon else None,
                            "duration": customer.coupon.duration if customer.coupon else None,
                            "duration_in_months": customer.coupon.duration_in_months if customer.coupon else None,
                        } if customer.coupon else None,
                        "start": customer.coupon_start,
                        "end": customer.coupon_end,
                    } if customer.coupon else None,
                }

                # Update subscription status with detailed information
                subscription_status.update(subscription_details)

            else:
                logger.info(f"No active subscription found for subdomain: {user.subdomain}")

        except Exception as e:
            logger.error(f"Error fetching subscription details: {str(e)}")
            logger.exception(e)

    except ZendeskUser.DoesNotExist:
        user = None

    # Define your price IDs
    PRICE_IDS = {
        "monthly": settings.STRIPE_PRICE_MONTHLY,
        "yearly": settings.STRIPE_PRICE_YEARLY,
    }

    context = {
        "subscription": subscription_status,
        "url_params": {
            "installation_id": installation_id,
            "plan": request.GET.get("plan", "Free"),
            "app_guid": app_guid,
            "origin": origin,
            "user_id": user_id,
        },
        "user": user,
        "environment": settings.ENVIRONMENT,
        "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,
        "price_ids": PRICE_IDS,
    }
    return render(request, "healthcheck/billing.html", context)


@csrf_exempt
def create_checkout_session(request):
    try:
        data = json.loads(request.body)
        installation_id = data.get("installation_id")
        user_id = data.get("user_id")
        plan_type = data.get("plan_type")
        price_id = data.get("price_id")

        if not all([installation_id, user_id, plan_type, price_id]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        # Get user information
        try:
            user = ZendeskUser.objects.get(user_id=user_id)
        except ZendeskUser.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)

        # Create Stripe checkout session
        stripe.api_key = settings.STRIPE_TEST_SECRET_KEY
        stripe.api_version = "2020-03-02"

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            client_reference_id=installation_id,
            customer_email=user.email,
            mode="subscription",
            allow_promotion_codes=True,
            billing_address_collection="required",
            automatic_tax={"enabled": True},
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            subscription_data={
                "metadata": {
                    "subdomain": user.subdomain,
                    "installation_id": installation_id,
                    "user_id": user_id,
                    "plan_type": plan_type,
                }
            },
            metadata={
                "installation_id": installation_id,
                "subdomain": user.subdomain,
                "user_id": user_id,
                "plan_type": plan_type,
            },
            success_url=request.build_absolute_uri(
                f"/billing/?installation_id={installation_id}&success=true"
            ),
            # cancel_url=request.build_absolute_uri(
            #     f"/billing/?installation_id={installation_id}&canceled=true"
            # ),
        )

        return JsonResponse({"url": checkout_session.url})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
