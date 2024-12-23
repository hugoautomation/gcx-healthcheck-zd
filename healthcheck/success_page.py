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
    """Handle successful subscription payments"""
    installation_id = request.GET.get("installation_id")

    if not installation_id:
        messages.error(request, "Missing installation ID")
        return HttpResponseRedirect("/")

    try:
        # Get the subscription from the session
        subscription = (
            Subscription.objects.filter(metadata__installation_id=installation_id)
            .order_by("-created")
            .first()
        )

        if not subscription:
            messages.warning(request, "Subscription not found")
            return HttpResponseRedirect(f"/billing/?installation_id={installation_id}")

        context = {
            "success": True,
            "subscription": {
                "plan_name": subscription.plan.product.name,
                "amount": subscription.plan.amount,
                "currency": subscription.plan.currency,
                "interval": subscription.plan.interval,
                "start_date": subscription.start_date,
                "current_period_end": subscription.current_period_end,
            },
            "customer": {
                "email": subscription.customer.email,
                "name": subscription.customer.name,
            },
            "installation_id": installation_id,
        }

        return render(request, "healthcheck/success/subscription_success.html", context)

    except Exception as e:
        logger.error(f"Error processing subscription success: {str(e)}")
        messages.error(request, "Error processing subscription")
        return HttpResponseRedirect(f"/billing/?installation_id={installation_id}")


@csrf_exempt
def one_off_success(request):
    """Handle successful one-off payments"""
    installation_id = request.GET.get("installation_id")
    payment_intent_id = request.GET.get("payment_intent")

    if not all([installation_id, payment_intent_id]):
        messages.error(request, "Missing required parameters")
        return HttpResponseRedirect("/")

    try:
        # Get the payment intent
        payment_intent = PaymentIntent.objects.get(id=payment_intent_id)

        context = {
            "success": True,
            "payment": {
                "amount": payment_intent.amount,
                "currency": payment_intent.currency,
                "status": payment_intent.status,
                "receipt_email": payment_intent.receipt_email,
                "created": payment_intent.created,
            },
            "installation_id": installation_id,
        }

        return render(request, "healthcheck/success/one_off_success.html", context)

    except PaymentIntent.DoesNotExist:
        messages.error(request, "Payment not found")
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