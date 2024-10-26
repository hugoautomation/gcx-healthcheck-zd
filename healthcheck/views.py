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
        print(data)
        response = requests.post(
            "https://app.configly.io/api/health-check/",
            headers={
                "Content-Type": "application/json",
                "X-API-Token": HEALTHCHECK_TOKEN,
            },
            json={
                "url": data.get("url"),
                "email": data.get("email"),
                "api_token": data.get("api_token"),
            },
        )
        print(response.json())
        
        # Render the template with the API response data
        html = render_to_string('healthcheck/results.html', {
            'data': response.json()
        })
        
        return HttpResponse(html)
