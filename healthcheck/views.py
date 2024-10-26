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
        print("Received data:", data)  # Debug log
        
        try:
            # Format the URL properly
            url = data.get("url")
            if not url.startswith('https://'):
                url = f'https://{url}'

            api_payload = {
                "url": url,
                "email": data.get("email"),
                "api_token": data.get("api_token"),
                "status": "active"  # Add status field
            }
            
            print("Sending payload:", api_payload)  # Debug log
            
            response = requests.post(
                "https://app.configly.io/api/health-check/",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Token": HEALTHCHECK_TOKEN,
                },
                json=api_payload
            )
            
            print("API Response Status:", response.status_code)  # Debug log
            print("API Response:", response.text)  # Debug log
            
            if response.status_code != 200:
                return HttpResponse(f"API Error: {response.text}", status=response.status_code)
            
            # Render the template with the API response data
            html = render_to_string('healthcheck/results.html', {
                'data': response.json()
            })
            
            return HttpResponse(html)
            
        except Exception as e:
            print("Error:", str(e))  # Debug log
            return HttpResponse(f"Error processing request: {str(e)}", status=500)
    
    return HttpResponse("Method not allowed", status=405)