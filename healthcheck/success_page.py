from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)
from healthcheck.models import HealthCheckReport

@csrf_exempt
def subscription_success(request):
        return render(request, "healthcheck/success/subscription_success.html")


@csrf_exempt
def one_off_success(request):
    """Handle successful one-off payments"""
    installation_id = request.GET.get("installation_id")
    report_id = request.GET.get("report_id")
    
    if not all([installation_id, report_id]):
        messages.error(request, "Missing required parameters")
        return HttpResponseRedirect("/")
        
    try:
        report = HealthCheckReport.objects.get(id=report_id)
        
        context = {
            "success": True,
            "report": {
                "id": report.id,
                "created_at": report.created_at,
            },
            "installation_id": installation_id,
            "report_id": report_id
        }
        
        return render(request, "healthcheck/success/one_off_success.html", context)
        
    except HealthCheckReport.DoesNotExist:
        messages.error(request, "Report not found")
        return HttpResponseRedirect(f"/billing/?installation_id={installation_id}")
    except Exception as e:
        logger.error(f"Error processing payment success: {str(e)}")
        messages.error(request, "Error processing payment")
        return HttpResponseRedirect(f"/billing/?installation_id={installation_id}")





@csrf_exempt
def test_subscription_success(request):
    """Test view for subscription success page"""
    mock_data = {
        "success": True,
        "subscription": {
            "plan_name": "Professional Plan",
            "amount": 119.00,
            "currency": "USD",
            "interval": "month",
            "start_date": timezone.now(),
            "current_period_end": timezone.now() + timezone.timedelta(days=30),
        },
        "customer": {
            "email": "test@example.com",
            "name": "Test User"
        },
        "installation_id": "12345"
    }
    return render(request, "healthcheck/success/subscription_success.html", mock_data)

@csrf_exempt
def test_one_off_success(request):
    """Test view for one-off payment success page"""
    mock_data = {
        "success": True,
        "payment": {
            "amount": 299.00,
            "currency": "USD",
            "status": "succeeded",
            "receipt_email": "test@example.com",
            "created": timezone.now()
        },
        "installation_id": "12345"
    }
    return render(request, "healthcheck/success/one_off_success.html", mock_data)