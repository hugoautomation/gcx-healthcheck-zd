from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
import requests
from zendeskapp import settings


def app(request):
    return render(request, "healthcheck/app.html")


@csrf_exempt
def health_check(request):
    if request.method == "POST":
        data = request.POST
        HEALTHCHECK_TOKEN = settings.HEALTHCHECK_TOKEN
        print("Received data:", data)

        try:
            url = data.get("url")
            if not url.startswith("https://"):
                url = f"https://{url}"

            api_payload = {
                "url": url,
                "email": data.get("email"),
                "api_token": data.get("api_token"),
                "status": "active",
            }

            print("Sending payload:", api_payload)

            response = requests.post(
                "https://app.configly.io/api/health-check/",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Token": HEALTHCHECK_TOKEN,
                },
                json=api_payload,
            )

            print("API Response Status:", response.status_code)
            print("API Response:", response.text)

            if response.status_code != 200:
                return HttpResponse(
                    render_to_string(
                        "healthcheck/results.html",
                        {"error": f"API Error: {response.text}"},
                    )
                )

            # Process the response data
            response_data = response.json()
            
            # Get instance details
            instance_info = {
                "name": response_data.get("name", "Unknown"),
                "url": response_data.get("instance_url", "Unknown"),
                "admin_email": response_data.get("admin_email", "Unknown"),
                "created_at": response_data.get("created_at", "Unknown"),
            }
            
            # Get counts
            counts = response_data.get("counts", {})
            total_counts = response_data.get("sum_totals", {})
            
            # Extract issues from the response
            issues = response_data.get("issues", [])
            
            if not isinstance(issues, list):
                raise ValueError(f"Unexpected issues format: {issues}")

            formatted_data = {
                "instance": instance_info,
                "total_issues": len(issues),
                "critical_issues": sum(
                    1 for issue in issues if issue.get("type") == "error"
                ),
                "warning_issues": sum(
                    1 for issue in issues if issue.get("type") == "warning"
                ),
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
                "issues": [
                    {
                        "category": issue.get("item_type", "Unknown"),
                        "severity": issue.get("type", "warning"),
                        "description": issue.get("message", ""),
                        "zendesk_url": issue.get("zendesk_url", "#"),
                    }
                    for issue in issues
                ] if issues else []
            }

            print("Formatted data:", formatted_data)

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