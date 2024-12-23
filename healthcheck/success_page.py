from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from djstripe.models import Subscription, PaymentIntent
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)


@csrf_exempt
def subscription_success(request):
        return render(request, "healthcheck/success/subscription_success.html")


@csrf_exempt
def one_off_success(request):
        return render(request, "healthcheck/success/one_off_success.html")





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