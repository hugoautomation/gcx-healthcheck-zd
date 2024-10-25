from django.shortcuts import render
from django.http import JsonResponse
import requests

def app(request):
    return render(request, 'healthcheck/app.html')

def health_check(request):
    if request.method == 'POST':
        data = request.POST
        HEALTHCHECK_TOKEN = 'your_token_here'
        
        response = requests.post(
            'https://app.configly.io/api/health-check/',
            headers={
                'Content-Type': 'application/json',
                'X-API-Token': HEALTHCHECK_TOKEN
            },
            json={
                'url': data.get('url'),
                'email': data.get('email'),
                'api_token': data.get('api_token')
            }
        )
        
        return JsonResponse(response.json())