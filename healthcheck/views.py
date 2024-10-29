from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json
import requests
from zendeskapp import settings
from .models import HealthCheckReport, HealthCheckMonitoring
from .utils import (
    format_response_data,
    get_monitoring_context,
    format_historical_reports,
    render_report_components,
)
import csv


# Update the app view to remove monitoring context
def app(request):
    initial_data = {}
    installation_id = request.GET.get("installation_id")
    client_plan = request.GET.get("plan", "Free")

    if installation_id:
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

                # Update initial data with report context only
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
                        "error": "No health check reports found. Please run your first health check.",
                        "historical_reports": [],
                        "data": None,
                    }
                )

        except Exception as e:
            print(f"Error in app view: {str(e)}")
            initial_data["error"] = f"Error loading health check data: {str(e)}"
    else:
        initial_data["error"] = "No installation ID provided. Please reload the app."

    return render(request, "healthcheck/app.html", initial_data)


@csrf_exempt
def health_check(request):
    if request.method == "POST":
        try:
            # Extract data from request
            data = json.loads(request.body) if request.body else {}
            installation_id = data.get("installation_id")
            client_plan = data.get("plan", "Free")

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

            response = requests.post(
                "https://app.configly.io/api/health-check/",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Token": settings.HEALTHCHECK_TOKEN,
                },
                json=api_payload,
            )

            if response.status_code != 200:
                error_data = {"error": f"API Error: {response.text}"}
                results_html, _ = render_report_components(error_data, {})
                return JsonResponse({"error": True, "results_html": results_html})

            # Get response data
            response_data = response.json()

            # Create report
            report = HealthCheckReport.objects.create(
                installation_id=int(installation_id),
                instance_guid=data.get("instance_guid"),
                subdomain=data.get("subdomain", ""),
                plan=client_plan,
                app_guid=data.get("app_guid"),
                stripe_subscription_id=data.get("stripe_subscription_id"),
                version=data.get("version", "1.0.0"),
                raw_response=response_data,
            )

            # Format response data
            formatted_data = format_response_data(
                response_data,
                plan=client_plan,
                report_id=report.id,
                last_check=report.created_at,
            )

            # Render results using utility function
            results_html, _ = render_report_components(formatted_data, {})

            return JsonResponse({"error": False, "results_html": results_html})

        except Exception as e:
            error_data = {"error": f"Error processing request: {str(e)}"}
            results_html, _ = render_report_components(error_data, {})
            return JsonResponse({"error": True, "results_html": results_html})

    return HttpResponse("Method not allowed", status=405)


def monitoring(request):
    installation_id = request.GET.get("installation_id")
    client_plan = request.GET.get("plan", "Free")

    if not installation_id:
        messages.error(request, "Installation ID required")
        return HttpResponseRedirect("/")

    context = get_monitoring_context(installation_id, client_plan, None)
    return render(request, "healthcheck/monitoring.html", context)


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

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

                print(f"Successfully unlocked report {report_id}")
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
            results_html, _ = render_report_components(report_data, {})

            return JsonResponse({"is_unlocked": True, "html": results_html})

        return JsonResponse({"is_unlocked": False})

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


def get_historical_report(request, report_id):
    """Fetch a historical report by ID"""
    try:
        report = HealthCheckReport.objects.get(id=report_id)
        installation_id = request.GET.get("installation_id")

        # Format the report data
        report_data = format_response_data(
            report.raw_response,
            plan=report.plan,
            report_id=report.id,
            last_check=report.created_at,
        )

        # Get monitoring context using utility function
        monitoring_context = get_monitoring_context(
            installation_id, report.plan, report
        )

        # Use render_report_components utility
        results_html, monitoring_html = render_report_components(
            report_data, monitoring_context
        )

        return JsonResponse(
            {"monitoring_html": monitoring_html, "results_html": results_html}
        )

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


@csrf_exempt
def monitoring_settings(request):
    """Handle monitoring settings updates"""
    installation_id = request.POST.get("installation_id")
    if not installation_id:
        messages.error(request, "Installation ID required")
        return HttpResponseRedirect(request.POST.get("redirect_url", "/"))

    # Get the latest report to check plan status
    latest_report = HealthCheckReport.get_latest_for_installation(installation_id)
    is_free_plan = latest_report.plan == "Free" if latest_report else True

    if request.method == "POST":
        if is_free_plan:
            messages.error(request, "Monitoring not available for free plan")
            return HttpResponseRedirect(request.POST.get("redirect_url", "/"))

        try:
            is_active = request.POST.get("is_active") == "on"
            frequency = request.POST.get("frequency", "weekly")
            notification_emails = request.POST.getlist("notification_emails[]")

            # Filter out empty email fields
            notification_emails = [
                email for email in notification_emails if email and email.strip()
            ]

            # Update or create monitoring settings
            monitoring, _ = HealthCheckMonitoring.objects.update_or_create(
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

            messages.success(request, "Settings saved successfully")

        except Exception as e:
            messages.error(request, f"Error saving settings: {str(e)}")

        return HttpResponseRedirect(request.POST.get("redirect_url", "/"))

    return HttpResponseRedirect(request.GET.get("redirect_url", "/"))


@csrf_exempt
def update_installation_plan(request):
    """Handle plan updates from Zendesk"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        installation_id = data.get("installation_id")
        new_plan = data.get("plan")

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

        return JsonResponse({"status": "success"})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
