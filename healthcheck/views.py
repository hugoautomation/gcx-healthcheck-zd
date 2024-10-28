import json
from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
import requests
from zendeskapp import settings
from .models import HealthCheckReport, ReportUnlock
from django.utils.timesince import timesince


def app(request):
    installation_id = request.GET.get("installation_id")
    print(f"Received installation_id: {installation_id}")

    initial_data = {}
    if installation_id:
        try:
            # Always get the latest report
            latest_report = HealthCheckReport.get_latest_for_installation(
                installation_id
            )
            if latest_report:
                initial_data = {
                    "data": format_response_data(
                        latest_report.raw_response,
                        last_check=latest_report.updated_at,
                        plan=latest_report.plan,
                        report_id=latest_report.id,
                    )
                }
                print(
                    f"Found latest report {latest_report.id} for installation {installation_id}"
                )
        except Exception as e:
            print(f"Error getting report: {str(e)}")
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
    # Filter issues for free plan
    if plan == "Free" and report_id:
        # Check if report is unlocked
        is_unlocked = ReportUnlock.objects.filter(report_id=report_id).exists()
        if not is_unlocked:
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
    if request.method == "POST":
        try:
            event = json.loads(request.body)
            if event["type"] == "checkout.session.completed":
                session = event["data"]["object"]
                report_id = session.get("client_reference_id")  # Changed from metadata

                if report_id:
                    # Create unlock record
                    ReportUnlock.objects.create(
                        report_id=report_id, stripe_payment_id=session["payment_intent"]
                    )

                return HttpResponse(status=200)
        except Exception as e:
            return HttpResponse(str(e), status=400)
    return HttpResponse(status=405)

def check_unlock_status(request):
    report_id = request.GET.get('report_id')
    if report_id:
        is_unlocked = ReportUnlock.objects.filter(report_id=report_id).exists()
        if is_unlocked:
            # If unlocked, return the full report HTML
            report = HealthCheckReport.objects.get(id=report_id)
            formatted_data = format_response_data(
                report.raw_response,
                plan=report.plan,
                report_id=report.id,
                last_check=report.updated_at
            )
            html = render_to_string('healthcheck/results.html', {'data': formatted_data})
            return HttpResponse(html)
    return HttpResponse(status=404)