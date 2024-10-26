from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
import requests
from zendeskapp import settings
from .models import HealthCheckReport


def app(request):
    return render(request, "healthcheck/app.html")

from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
import requests
import json
from zendeskapp import settings
from .models import HealthCheckReport


def app(request):
    return render(request, "healthcheck/app.html")

from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
import requests
import json
from zendeskapp import settings
from .models import HealthCheckReport


def app(request):
    return render(request, "healthcheck/app.html")


@csrf_exempt
def health_check(request):
    if request.method == "POST":
        try:
            # Extract data from request
            data = json.loads(request.body) if request.body else request.POST
            print("Received data:", data)

            # Prepare URL
            url = data.get("url")
            if not url.startswith("https://"):
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

            # Save report to database
            report = HealthCheckReport.objects.create(
                instance_guid=data.get('instance_guid'),
                installation_id=data.get('installation_id'),
                subdomain=data.get('subdomain', ''),
                plan=data.get('plan'),
                stripe_subscription_id=data.get('stripe_subscription_id'),
                version=data.get('version', '1.0.0'),
                raw_response=response_data
            )
            print(f"Saved report {report.id} for {report.subdomain}")

            # Process response data for template
            issues = response_data.get("issues", [])
            counts = response_data.get("counts", {})
            total_counts = response_data.get("sum_totals", {})

            formatted_data = {
                "instance": {
                    "name": response_data.get("name", "Unknown"),
                    "url": response_data.get("instance_url", "Unknown"),
                    "admin_email": response_data.get("admin_email", "Unknown"),
                    "created_at": response_data.get("created_at", "Unknown"),
                },
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
                'categories': sorted(set(issue.get('item_type', 'Unknown') for issue in issues)),
                "issues": [
                    {
                        "category": issue.get("item_type", "Unknown"),
                        "severity": issue.get("type", "warning"),
                        "description": issue.get("message", ""),
                        "zendesk_url": issue.get("zendesk_url", "#"),
                    }
                    for issue in issues
                ]
            }

            # Render template
            html = render_to_string(
                "healthcheck/results.html", 
                {"data": formatted_data}
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