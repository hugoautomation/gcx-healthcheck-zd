import json
from django.http import JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
import requests
from zendeskapp import settings
from .models import HealthCheckReport, HealthCheckMonitoring
from django.utils.timesince import timesince
import csv


def app(request):
    initial_data = {}

    # Get installation_id and report_id from the request parameters
    installation_id = request.GET.get("installation_id")
    report_id = request.GET.get("report_id")

    if installation_id:
        try:
            # Get historical reports for this installation
            historical_reports = HealthCheckReport.objects.filter(
                installation_id=installation_id
            ).order_by("-created_at")[:10]

            # Get the current report (either specified by ID or latest)
            if report_id:
                current_report = HealthCheckReport.objects.get(id=report_id)
            else:
                # Use the helper method to get latest report
                current_report = HealthCheckReport.get_latest_for_installation(
                    installation_id
                )

            if current_report:
                report_data = format_response_data(
                    current_report.raw_response,
                    plan=current_report.plan,
                    report_id=current_report.id,
                    last_check=current_report.created_at,
                )

            initial_data.update(
                {
                    "historical_reports": [
                        {
                            "id": report.id,
                            "created_at": report.created_at.strftime("%d %b %Y"),
                            "is_unlocked": report.is_unlocked,
                            "total_issues": len(report.raw_response.get("issues", [])),
                        }
                        for report in historical_reports
                    ],
                    "data": report_data if current_report else None,
                }
            )

        except Exception as e:
            print(f"Error getting reports: {str(e)}")
            pass

    return render(request, "healthcheck/app.html", initial_data)


@csrf_exempt
def health_check(request):
    if request.method == "POST":
        try:
            # Extract data from request
            data = json.loads(request.body) if request.body else {}
            print("Received data:", data)

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

            print("API Response Status:", response.status_code)

            if response.status_code != 200:
                return HttpResponse(
                    render_to_string(
                        "healthcheck/results.html",
                        {"error": f"API Error: {response.text}"},
                    )
                )

            # Get response data
            response_data = response.json()

            # Update or create report in database
            report = HealthCheckReport.objects.create(
                installation_id=int(data.get("installation_id", 0)),
                instance_guid=data.get("instance_guid"),
                subdomain=data.get("subdomain", ""),
                plan=data.get("plan"),
                app_guid=data.get("app_guid"),
                stripe_subscription_id=data.get("stripe_subscription_id"),
                version=data.get("version", "1.0.0"),
                raw_response=response_data,
            )

            print(f"Created new report {report.id} for {report.subdomain}")

            # Process response data for template
            formatted_data = format_response_data(
                response_data, plan=data.get("plan", "Free"), report_id=report.id
            )
            # Render template
            html = render_to_string(
                "healthcheck/results.html", {"data": formatted_data}
            )

            return HttpResponse(html)

        except Exception as e:
            print("Error:", str(e))
            return HttpResponse(
                render_to_string(
                    "healthcheck/results.html",
                    {"error": f"Error processing request: {str(e)}"},
                )
            )

    return HttpResponse("Method not allowed", status=405)


def format_response_data(response_data, plan="Free", report_id=None, last_check=None):
    """Helper function to format response data consistently"""
    issues = response_data.get("issues", [])
    counts = response_data.get("counts", {})
    total_counts = response_data.get("sum_totals", {})

    # Calculate hidden issues for free plan
    hidden_issues_count = 0
    hidden_categories = {}

    if plan == "Free" and report_id:
        try:
            report = HealthCheckReport.objects.get(id=report_id)
            is_unlocked = report.is_unlocked
        except HealthCheckReport.DoesNotExist:
            is_unlocked = False

        if not is_unlocked:
            # Count issues by category before filtering
            for issue in issues:
                category = issue.get("item_type")
                if category not in ["ticket_forms", "ticket_fields"]:
                    hidden_issues_count += 1
                    hidden_categories[category] = hidden_categories.get(category, 0) + 1

            # Filter issues for display
            issues = [
                issue
                for issue in issues
                if issue.get("item_type") in ["ticket_forms", "ticket_fields"]
            ]

    return {
        "instance": {
            "name": response_data.get("name", "Unknown"),
            "url": response_data.get("instance_url", "Unknown"),
            "admin_email": response_data.get("admin_email", "Unknown"),
            "created_at": response_data.get("created_at", "Unknown"),
        },
        "last_check": last_check.strftime("%Y-%m-%d %H:%M:%S") if last_check else None,
        "time_since_check": timesince(last_check) if last_check else "Never",
        "total_issues": len(issues),
        "critical_issues": sum(1 for issue in issues if issue.get("type") == "error"),
        "warning_issues": sum(1 for issue in issues if issue.get("type") == "warning"),
        "counts": {
            "ticket_fields": counts.get("ticket_fields", {}),
            "user_fields": counts.get("user_fields", {}),
            "organization_fields": counts.get("organization_fields", {}),
            "ticket_forms": counts.get("ticket_forms", {}),
            "triggers": counts.get("ticket_triggers", {}),
            "macros": counts.get("macros", {}),
            "users": counts.get("zendesk_users", {}),
            "sla_policies": counts.get("sla_policies", {}),
        },
        "totals": {
            "total": total_counts.get("sum_total", 0),
            "draft": total_counts.get("sum_draft", 0),
            "published": total_counts.get("sum_published", 0),
            "changed": total_counts.get("sum_changed", 0),
            "deletion": total_counts.get("sum_deletion", 0),
            "total_changes": total_counts.get("sum_total_changes", 0),
        },
        "categories": sorted(
            set(issue.get("item_type", "Unknown") for issue in issues)
        ),
        "hidden_issues_count": hidden_issues_count,
        "hidden_categories": hidden_categories,
        "is_free_plan": plan == "Free",
        "is_unlocked": is_unlocked if plan == "Free" else True,
        "report_id": report_id,
        "issues": [
            {
                "category": issue.get("item_type", "Unknown"),
                "severity": issue.get("type", "warning"),
                "description": issue.get("message", ""),
                "zendesk_url": issue.get("zendesk_url", "#"),
            }
            for issue in issues
        ],
    }


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

            # Render the template with full data
            html = render_to_string("healthcheck/results.html", {"data": report_data})

            return JsonResponse({"is_unlocked": True, "html": html})

        return JsonResponse({"is_unlocked": False})

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


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

        # Render the template with the data
        html = render_to_string("healthcheck/results.html", {"data": report_data})

        return JsonResponse({"html": html})

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


@csrf_exempt
def monitoring_settings(request):
    """Handle monitoring settings updates"""
    installation_id = request.GET.get("installation_id")
    if not installation_id:
        return JsonResponse({"error": "Installation ID required"}, status=400)

    if request.method == "GET":
        try:
            monitoring = HealthCheckMonitoring.objects.get(
                installation_id=installation_id
            )
            return JsonResponse(
                {
                    "is_active": monitoring.is_active,
                    "frequency": monitoring.frequency,
                    "notification_emails": monitoring.notification_emails,
                }
            )
        except HealthCheckMonitoring.DoesNotExist:
            return JsonResponse(
                {
                    "is_active": False,
                    "frequency": "weekly",
                    "notification_emails": [],
                }
            )

    elif request.method == "POST":
        data = json.loads(request.body)
        monitoring, created = HealthCheckMonitoring.objects.update_or_create(
            installation_id=installation_id,
            defaults={
                "instance_guid": data.get("instance_guid"),
                "subdomain": data.get("subdomain"),
                "is_active": data.get("is_active", True),
                "frequency": data.get("frequency", "weekly"),
                "notification_emails": data.get("notification_emails", []),
            },
        )
        return JsonResponse({"status": "success"})

    return JsonResponse({"error": "Method not allowed"}, status=405)
