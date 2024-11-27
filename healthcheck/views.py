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
    client_plan = request.GET.get("plan", "Free")
    app_guid = request.GET.get("app_guid")
    origin = request.GET.get("origin")
    user_id = request.GET.get("user_id")

    initial_data.update(
        {
            "url_params": {
                "installation_id": installation_id,
                "plan": client_plan,
                "app_guid": app_guid,
                "origin": origin,
                "user_id": user_id,
            },
            "environment": settings.ENVIRONMENT,  # Add environment to context
        }
    )

    if installation_id:
        historical_reports = HealthCheckReport.objects.filter(
            installation_id=installation_id
        ).order_by("-created_at")[:10]

        latest_report = HealthCheckReport.get_latest_for_installation(installation_id)

        user = ZendeskUser.objects.get(user_id=user_id)

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
                "plan": user.plan or client_plan,
                "installation_id": installation_id,
                "last_healthcheck": latest_report.created_at if latest_report else None,
                "last_healthcheck_paid_for": latest_report.is_unlocked
                if latest_report
                else False,
            },
        )
        analytics.group(
            user_id,  # The user ID that belongs to the group
            user.subdomain,
            {
                "name": user.subdomain,
                "organization": user.subdomain,
                "plan": user.plan or client_plan,
            },
        )
        # Track app load
        analytics.track(
            user_id,  # Use user_id if available
            "App Loaded",
            {
                "plan": client_plan,
                "subdomain": origin,
                "installation_id": installation_id,
            },
        )

        try:
            # Get historical reports
            historical_reports = HealthCheckReport.objects.filter(
                installation_id=installation_id
            ).order_by("-created_at")[:10]

            # Get latest report
            latest_report = HealthCheckReport.get_latest_for_installation(
                installation_id
            )

            if latest_report:
                # Update unlock status for non-free plans
                if client_plan != "Free":
                    HealthCheckReport.update_all_reports_unlock_status(
                        installation_id, client_plan
                    )

                # Format the report data
                report_data = format_response_data(
                    latest_report.raw_response,
                    plan=client_plan,
                    report_id=latest_report.id,
                    last_check=latest_report.created_at,
                )

                # Update initial data with report context
                initial_data.update(
                    {
                        "historical_reports": format_historical_reports(
                            historical_reports
                        ),
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
            initial_data["error"] = f"Error loading health check data: {
                str(e)}"
    else:
        initial_data["error"] = "No installation ID provided. Please reload the app."

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
            client_plan = data.get("plan", "Free")
            user_id = data.get("user_id")  # Get user_id from request data

            analytics.track(
                user_id,
                "Health Check Started",
                {
                    "subdomain": data.get("subdomain"),
                    "email": data.get("email"),
                    "plan": data.get("plan", "Free"),
                },
            )

            # Prepare URL
            url = data.get("url")
            if not url or not url.startswith("https://"):
                url = f"https://{url}"

            # Make API request
            api_payload = {
                "url": url,
                "email": data.get("email"),
                "api_token": data.get("api_token"),
                "status": "active",
            }
            api_url = (
                "https://app.configly.io/api/health-check/"
                if settings.ENVIRONMENT == "production"
                else "https://django-server-development-1b87.up.railway.app/api/health-check/"
            )

            response = requests.post(
                api_url,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Token": settings.HEALTHCHECK_TOKEN,
                },
                json=api_payload,
            )

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
                plan=client_plan,
                app_guid=data.get("app_guid"),
                stripe_subscription_id=data.get("stripe_subscription_id"),
                version=data.get("version", "1.0.0"),
                raw_response=response_data,
            )
            user = ZendeskUser.objects.get(user_id=user_id)
            analytics.identify(
                user_id,
                {
                    "email": user.email,
                    "last_healthcheck": report.created_at,
                },
            )
            # Format response data
            formatted_data = format_response_data(
                response_data,
                plan=client_plan,
                report_id=report.id,
                last_check=report.created_at,
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
                    "is_unlocked": report.is_unlocked,  # Add unlock status
                    "plan": client_plan,
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
        context = get_monitoring_context(installation_id, client_plan, None)
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
def stripe_webhook(request):
    try:
        event = json.loads(request.body)
        print("Received webhook event:", event["type"])  # Debug logging

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            report_id = session.get("client_reference_id")

            if not report_id:
                print("No report ID provided in webhook")
                return HttpResponse("No report ID provided", status=400)

            try:
                report = HealthCheckReport.objects.get(id=report_id)
                report.is_unlocked = True
                report.stripe_payment_id = session["payment_intent"]
                report.save()

                user_id = session.get("userInfo", {}).get("id")
                user = ZendeskUser.objects.get(user_id=user_id)
                print(f"Successfully unlocked report {report_id}")
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
                        "plan": user.plan,
                        "last_healthcheck": report.created_at,
                        "last_healthcheck_paid_for": report.is_unlocked,
                    },
                )
                analytics.track(
                    str(user_id),
                    "Report Unlocked",
                    {
                        "report_id": report_id,
                        "payment_amount": 249,
                        "payment_type": "one_off",
                    },
                )
                return HttpResponse("Success", status=200)

            except HealthCheckReport.DoesNotExist:
                print(f"Report {report_id} not found")
                return HttpResponse("Report not found", status=404)

    except json.JSONDecodeError:
        print("Invalid JSON in webhook request")
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return HttpResponse(str(e), status=400)


@csrf_exempt
def download_report_csv(request, report_id):
    """Download health check report as CSV"""
    try:
        report = HealthCheckReport.objects.get(id=report_id)
        # Get user_id from request parameters
        user_id = request.GET.get("user_id")

        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="healthcheck_report_{report_id}.csv"'
        )
        # analytics.track(
        #     user_id,
        #     "Report CSV Downloaded",
        #     {"report_id": report_id},
        # )

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

        if report.is_unlocked:
            # Format the full report data
            report_data = format_response_data(
                report.raw_response,
                plan=report.plan,
                report_id=report.id,
                last_check=report.created_at,
            )

            # Use render_report_components utility
            results_html = render_report_components(report_data)

            return JsonResponse({"is_unlocked": True, "html": results_html})

        return JsonResponse({"is_unlocked": False})

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


@csrf_exempt
def get_historical_report(request, report_id):
    """Fetch a historical report by ID"""
    try:
        report = HealthCheckReport.objects.get(id=report_id)

        # Format the report data
        report_data = format_response_data(
            report.raw_response,
            plan=report.plan,
            report_id=report.id,
            last_check=report.created_at,
        )

        # Use render_report_components utility
        results_html = render_report_components(report_data)

        return JsonResponse({"results_html": results_html})

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


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

    # GET request - render the monitoring page
    context = get_monitoring_context(
        installation_id, latest_report.plan if latest_report else "Free", None
    )
    context["url_params"] = {
        "installation_id": installation_id,
        "plan": latest_report.plan if latest_report else "Free",
    }

    return render(request, "healthcheck/monitoring.html", context)


@csrf_exempt
def update_installation_plan(request):
    """Handle plan updates from Zendesk"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        installation_id = data.get("installation_id")
        new_plan = data.get("plan")
        user_id = data.get("user_id")  # Get user_id from request

        if not installation_id or not new_plan:
            return JsonResponse({"error": "Missing required fields"}, status=400)

        # Update the latest report's plan
        HealthCheckReport.update_latest_report_plan(installation_id, new_plan)

        # Update monitoring settings if downgrading to free plan
        if new_plan == "Free":
            try:
                monitoring = HealthCheckMonitoring.objects.get(
                    installation_id=installation_id
                )
                monitoring.is_active = False  # Disable monitoring for free plan
                monitoring.save()
            except HealthCheckMonitoring.DoesNotExist:
                pass
        analytics.track(
            user_id,
            "Plan Updated",
            {
                "new_plan": new_plan,
                "previous_plan": HealthCheckReport.get_latest_for_installation(
                    installation_id
                ).plan,
            },
        )
        return JsonResponse({"status": "success"})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
