from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

import json
from zendeskapp import settings
from ..models import HealthCheckReport, HealthCheckMonitoring, ZendeskUser
from ..utils.stripe import (
    get_default_subscription_status,
)

import segment.analytics as analytics  # Add this import
import logging
import stripe
from djstripe.event_handlers import djstripe_receiver
from django.db import transaction
from djstripe.models import Event, Subscription
from ..cache_utils import HealthCheckCache, invalidate_app_cache

if settings.DJANGO_ENV == "production":
    stripe.api_key = settings.STRIPE_LIVE_SECRET_KEY
else:
    stripe.api_key = settings.STRIPE_TEST_SECRET_KEY


logger = logging.getLogger(__name__)


@csrf_exempt
def billing_page(request):
    installation_id = request.GET.get("installation_id")
    user_id = request.GET.get("user_id")
    app_guid = request.GET.get("app_guid")
    origin = request.GET.get("origin")
    subscription_status = get_default_subscription_status()
    if settings.DJANGO_ENV == "production":
        stripe_portal = "https://billing.stripe.com/p/login/cN26qO86Hc7b3YI5kk"
    else:
        stripe_portal = "https://billing.stripe.com/p/login/test_4gwaHHgWTeitgsUfYY"

    # Show loading state if no installation_id
    if not installation_id:
        return render(
            request,
            "healthcheck/billing.html",
            {
                "loading": "Loading your workspace...",
                "environment": settings.ENVIRONMENT,
            },
        )
    try:
        user = ZendeskUser.objects.get(user_id=user_id)
        subscription_status = HealthCheckCache.get_subscription_status(user.subdomain)
        # Get detailed subscription information
        try:
            # First try to get active or trialing subscription
            active_subscription = Subscription.objects.filter(
                metadata__subdomain=user.subdomain, status__in=["active", "trialing"]
            ).first()

            # Get customer if there's an active subscription
            if active_subscription:
                customer = active_subscription.customer
                latest_invoice = active_subscription.latest_invoice

                subscription_details = {
                    # Basic subscription info
                    "status": active_subscription.status,
                    "current_period_start": active_subscription.current_period_start,
                    "current_period_end": active_subscription.current_period_end,
                    "start_date": active_subscription.start_date,
                    "cancel_at_period_end": active_subscription.cancel_at_period_end,
                    "ended_at": active_subscription.ended_at,
                    "cancel_at": active_subscription.cancel_at,
                    "canceled_at": active_subscription.canceled_at,
                    "trial_start": active_subscription.trial_start,
                    "trial_end": active_subscription.trial_end,
                    # Plan details
                    "plan": {
                        "id": active_subscription.plan.id,
                        "nickname": active_subscription.plan.nickname,
                        "amount": active_subscription.plan.amount,
                        "interval": active_subscription.plan.interval,
                        "product_name": active_subscription.plan.product.name,
                        "currency": active_subscription.plan.currency,
                    },
                    # Customer details
                    "customer": {
                        "name": customer.name,
                        "email": customer.email,
                        "address": customer.address,
                        "currency": customer.currency,
                        "balance": customer.balance,
                        "delinquent": customer.delinquent,
                        "default_payment_method": {
                            "type": customer.default_payment_method.type
                            if customer.default_payment_method
                            else None,
                            "card_brand": customer.default_payment_method.card.brand
                            if customer.default_payment_method
                            and hasattr(customer.default_payment_method, "card")
                            else None,
                            "card_last4": customer.default_payment_method.card.last4
                            if customer.default_payment_method
                            and hasattr(customer.default_payment_method, "card")
                            else None,
                        }
                        if customer.default_payment_method
                        else None,
                    },
                    # Invoice details
                    "latest_invoice": {
                        "number": latest_invoice.number if latest_invoice else None,
                        "amount_due": latest_invoice.amount_due
                        if latest_invoice
                        else None,
                        "amount_paid": latest_invoice.amount_paid
                        if latest_invoice
                        else None,
                        "hosted_invoice_url": latest_invoice.hosted_invoice_url
                        if latest_invoice
                        else None,
                        "pdf_url": latest_invoice.invoice_pdf
                        if latest_invoice
                        else None,
                        "status": latest_invoice.status if latest_invoice else None,
                    }
                    if latest_invoice
                    else None,
                    # Discount information
                    "discount": {
                        "coupon": {
                            "amount_off": customer.coupon.amount_off
                            if customer.coupon
                            else None,
                            "percent_off": customer.coupon.percent_off
                            if customer.coupon
                            else None,
                            "duration": customer.coupon.duration
                            if customer.coupon
                            else None,
                            "duration_in_months": customer.coupon.duration_in_months
                            if customer.coupon
                            else None,
                        }
                        if customer.coupon
                        else None,
                        "start": customer.coupon_start,
                        "end": customer.coupon_end,
                    }
                    if customer.coupon
                    else None,
                }

                # Update subscription status with detailed information
                subscription_status.update(subscription_details)

            else:
                logger.info(
                    f"No active subscription found for subdomain: {user.subdomain}"
                )

        except Exception as e:
            logger.error(f"Error fetching subscription details: {str(e)}")
            logger.exception(e)

    except ZendeskUser.DoesNotExist:
        user = None

    # Define your price IDs
    PRICE_IDS = {
        "monthly": settings.STRIPE_PRICE_MONTHLY,
        "yearly": settings.STRIPE_PRICE_YEARLY,
    }

    context = {
        "subscription": subscription_status,
        "url_params": {
            "installation_id": installation_id,
            "plan": request.GET.get("plan", "Free"),
            "app_guid": app_guid,
            "origin": origin,
            "user_id": user_id,
        },
        "stripe_portal": stripe_portal,
        "user": user,
        "environment": settings.ENVIRONMENT,
        "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,
        "price_ids": PRICE_IDS,
    }

    return render(request, "healthcheck/billing.html", context)


# At the top of the file, modify the Stripe key setup
if settings.DJANGO_ENV == "production":
    stripe.api_key = settings.STRIPE_LIVE_SECRET_KEY
else:
    stripe.api_key = settings.STRIPE_TEST_SECRET_KEY

logger = logging.getLogger(__name__)


@csrf_exempt
def create_checkout_session(request):
    try:
        data = json.loads(request.body)
        installation_id = data.get("installation_id")
        user_id = data.get("user_id")
        price_id = data.get("price_id")

        if not all([installation_id, user_id, price_id]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        # Get user information
        try:
            user = ZendeskUser.objects.get(user_id=user_id)
        except ZendeskUser.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)

        # Log the environment and price ID for debugging
        logger.info(f"Environment: {settings.DJANGO_ENV}")
        logger.info(f"Using price ID: {price_id}")
        logger.info(
            f"Using Stripe key: {'Live' if settings.DJANGO_ENV == 'production' else 'Test'}"
        )

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            allow_promotion_codes=True,
            billing_address_collection="required",
            automatic_tax={"enabled": True},
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            subscription_data={
                "metadata": {
                    "subdomain": user.subdomain,
                    "installation_id": installation_id,
                    "user_id": user_id,
                }
            },
            metadata={
                "installation_id": installation_id,
                "subdomain": user.subdomain,
                "user_id": user_id,
            },
            success_url=request.build_absolute_uri("/payment/subscription/success/"),
        )

        return JsonResponse({"url": checkout_session.url})

    except Exception as e:
        logger.error(f"Checkout session error: {str(e)}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=400)


@djstripe_receiver("checkout.session.completed")
def handle_checkout_completed(event: Event, **kwargs):
    """Handle successful checkout session completion"""
    try:
        # Log the entire event for debugging
        logger.info(f"Received checkout.session.completed webhook event: {event.id}")
        logger.info(f"Full event data: {event.data}")

        # Get the checkout session
        checkout_session = event.data.get("object", {})

        if not checkout_session:
            logger.error("No checkout session found in event data")
            return HttpResponse(status=400)

        # Log checkout session details
        logger.info(f"Checkout session ID: {checkout_session.get('id')}")
        logger.info(f"Payment status: {checkout_session.get('payment_status')}")

        # Extract and log metadata
        metadata = checkout_session.get("metadata", {})
        logger.info(f"Metadata received: {metadata}")

        report_id = metadata.get("report_id")
        subdomain = metadata.get("subdomain")
        user_id = metadata.get("user_id")
        installation_id = metadata.get("installation_id")
        invalidate_app_cache(installation_id)

        logger.info(
            f"Extracted data - Report ID: {report_id}, Subdomain: {subdomain}, User ID: {user_id}"
        )

        # Verify payment status
        payment_status = checkout_session.get("payment_status")
        if payment_status != "paid":
            logger.error(f"Unexpected payment status: {payment_status}")
            return HttpResponse(status=400)

        if not all([report_id, subdomain]):
            logger.error("Missing required metadata in checkout session")
            return HttpResponse(status=400)

        # Use transaction to ensure database consistency
        with transaction.atomic():
            try:
                logger.info(
                    f"Attempting to find report with ID: {report_id} and subdomain: {subdomain}"
                )
                report = HealthCheckReport.objects.get(
                    id=report_id, subdomain=subdomain
                )

                logger.info(
                    f"Found report, current unlock status: {report.is_unlocked}"
                )
                report.is_unlocked = True
                report.stripe_payment_id = checkout_session.get("id")
                report.save()  # Removed skip_others=True
                logger.info(
                    f"Successfully updated report {report_id} unlock status to True"
                )

                # Track the successful payment
                def track_payment():
                    logger.info(f"Tracking payment for report {report_id}")
                    analytics.track(
                        user_id,
                        "Report Unlocked",
                        {
                            "report_id": report_id,
                            "payment_id": checkout_session.get("id"),
                            "amount": checkout_session.get("amount_subtotal", 0) / 100,
                            "subdomain": subdomain,
                            "discount_amount": checkout_session.get(
                                "total_details", {}
                            ).get("amount_discount", 0)
                            / 100,
                            "final_amount": checkout_session.get("amount_total", 0)
                            / 100,
                        },
                    )

                transaction.on_commit(track_payment)
                logger.info(f"Successfully processed webhook for report {report_id}")
                return HttpResponse(status=200)

            except HealthCheckReport.DoesNotExist:
                logger.error(f"Report {report_id} not found for subdomain {subdomain}")
                return HttpResponse(status=404)

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=400)


@djstripe_receiver("customer.subscription.created")
@djstripe_receiver("customer.subscription.updated")
@djstripe_receiver("customer.subscription.deleted")
def handle_subscription_update(event: Event, **kwargs):
    """Handle subscription updates from Stripe"""
    try:
        logger.info(f"Received subscription webhook event: {event.type}")
        logger.info(f"Full event data: {event.data}")

        subscription = event.data["object"]
        metadata = subscription.get("metadata", {})

        # Extract metadata
        user_id = metadata.get("user_id")
        subdomain = metadata.get("subdomain")
        installation_id = metadata.get("installation_id")
        invalidate_app_cache(installation_id)

        # Invalidate subscription cache
        HealthCheckCache.invalidate_subscription_data(user_id, subdomain)

        if not all([user_id, subdomain]):
            logger.error(
                f"Missing required metadata. user_id: {user_id}, subdomain: {subdomain}"
            )
            return HttpResponse(status=400)

        # Get subscription status
        status = subscription.get("status")
        is_active = status in ["active", "trialing"]
        plan_id = subscription.get("plan", {}).get("id")

        logger.info(
            f"Subscription status for {subdomain}: {status}, is_active: {is_active}"
        )

        try:
            # Verify subdomain exists
            if not ZendeskUser.objects.filter(subdomain=subdomain).exists():
                logger.error(f"User not found for subdomain: {subdomain}")
                return HttpResponse(status=404)

            # Only update reports that haven't been individually unlocked
            affected_reports = HealthCheckReport.objects.filter(
                subdomain=subdomain,  # Only update subscription-based reports
            ).update(is_unlocked=True)

            logger.info(
                f"Updated {affected_reports} subscription-based reports for {subdomain} to is_unlocked={is_active}"
            )

            # Update monitoring settings if subscription is inactive
            if not is_active and installation_id:
                try:
                    monitoring = HealthCheckMonitoring.objects.get(
                        installation_id=installation_id
                    )
                    monitoring.is_active = False
                    monitoring.save()
                    logger.info(
                        f"Updated monitoring status for installation {installation_id}"
                    )
                except HealthCheckMonitoring.DoesNotExist:
                    logger.info(
                        f"No monitoring settings found for installation {installation_id}"
                    )

            # Track the event with additional info about affected reports
            analytics.track(
                user_id,
                "Subscription Status Updated",
                {
                    "event_type": event.type,
                    "subscription_status": status,
                    "subscription_active": is_active,
                    "plan": plan_id,
                    "subdomain": subdomain,
                    "installation_id": installation_id,
                    "affected_reports_count": affected_reports,
                    "individually_unlocked_reports_preserved": True,
                },
            )

            logger.info(
                f"Successfully processed subscription update for subdomain {subdomain}. "
                f"Updated {affected_reports} subscription-based reports. "
                f"Individually unlocked reports were preserved."
            )

            return HttpResponse(status=200)

        except Exception as e:
            logger.error(f"Database error: {str(e)}", exc_info=True)
            return HttpResponse(status=500)

    except Exception as e:
        logger.error(f"Error processing subscription webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=400)


@csrf_exempt
def create_payment_intent(request):
    try:
        data = json.loads(request.body)
        report_id = data.get("report_id")
        installation_id = data.get("installation_id")
        user_id = data.get("user_id")

        if not all([report_id, installation_id, user_id]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        # Get user information
        user = ZendeskUser.objects.get(user_id=user_id)

        # Create Stripe checkout session for one-time payment
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            allow_promotion_codes=True,
            billing_address_collection="required",
            automatic_tax={"enabled": True},
            line_items=[{"price": settings.ONE_OFF_UNLOCK_PRICE, "quantity": 1}],
            metadata={
                "report_id": report_id,
                "installation_id": installation_id,
                "user_id": user_id,
                "subdomain": user.subdomain,
            },
            success_url=request.build_absolute_uri(
                f"/payment/one-off/success/?installation_id={installation_id}&report_id={report_id}"
            ),
        )

        return JsonResponse({"url": checkout_session.url})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
