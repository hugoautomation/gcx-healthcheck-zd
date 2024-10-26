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
            print("API Response:", response.text)  # Add this for debugging

            if response.status_code != 200:
                return HttpResponse(
                    render_to_string(
                        "healthcheck/results.html",
                        {"error": f"API Error: {response.text}"},
                    )
                )

            # Process the response data
            issues = response.json()
            
            # Verify we have valid data
            if not isinstance(issues, list):
                raise ValueError(f"Unexpected API response format: {issues}")

            formatted_data = {
                "total_issues": len(issues),
                "critical_issues": sum(
                    1 for issue in issues if issue.get("type") == "error"
                ),
                "warning_issues": sum(
                    1 for issue in issues if issue.get("type") == "warning"
                ),
                "issues": [
                    {
                        "category": issue.get("item_type", "Unknown"),
                        "severity": issue.get("type", "warning"),
                        "description": issue.get("message", ""),
                        "edit_url": issue.get("edit_url", "#"),
                    }
                    for issue in issues
                ] if issues else []  # Ensure we handle empty lists properly
            }

            print("Formatted data:", formatted_data)  # Add this for debugging

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
