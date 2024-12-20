from djstripe.event_handlers import djstripe_receiver
from djstripe.models import Event
from .models import HealthCheckSubscription, HealthCheckReport, HealthCheckMonitoring
import segment.analytics as analytics

@djstripe_receiver("checkout.session.completed")
def handle_checkout_completed(sender, event: Event, **kwargs):
    """Handle successful checkout completion"""
    session = event.data["object"]
    installation_id = session["metadata"].get("installation_id")
    user_id = session["metadata"].get("user_id")
    subscription = event.data["object"].subscription

    if installation_id and subscription:
        # Link the subscription to the installation
        HealthCheckSubscription.link_subscription(
            installation_id=int(installation_id),
            djstripe_subscription=subscription
        )

        # Update the latest report's plan
        latest_report = HealthCheckReport.get_latest_for_installation(int(installation_id))
        if latest_report:
            latest_report.plan = subscription.plan.nickname
            latest_report.is_unlocked = True
            latest_report.save()

        # Track the event with Segment
        if user_id:
            analytics.track(
                str(user_id),
                "Subscription Created",
                {
                    "installation_id": installation_id,
                    "plan": subscription.plan.nickname,
                    "status": subscription.status
                }
            )

@djstripe_receiver("customer.subscription.updated")
def handle_subscription_updated(sender, event: Event, **kwargs):
    """Handle subscription updates"""
    subscription = event.data["object"]
    try:
        health_sub = HealthCheckSubscription.objects.get(
            subscription__id=subscription.id
        )
        # Update latest report plan
        latest_report = HealthCheckReport.get_latest_for_installation(
            health_sub.installation_id
        )
        if latest_report:
            latest_report.plan = subscription.plan.nickname
            latest_report.save()

    except HealthCheckSubscription.DoesNotExist:
        pass

@djstripe_receiver("customer.subscription.deleted")
def handle_subscription_deleted(sender, event: Event, **kwargs):
    """Handle subscription deletions"""
    subscription = event.data["object"]
    try:
        health_sub = HealthCheckSubscription.objects.get(
            subscription__id=subscription.id
        )
        
        # Update to free plan
        latest_report = HealthCheckReport.get_latest_for_installation(
            health_sub.installation_id
        )
        if latest_report:
            latest_report.plan = "Free"
            latest_report.save()

        # Disable monitoring for free plan
        try:
            monitoring = HealthCheckMonitoring.objects.get(
                installation_id=health_sub.installation_id
            )
            monitoring.is_active = False
            monitoring.save()
        except HealthCheckMonitoring.DoesNotExist:
            pass

        # Clear the subscription reference
        health_sub.subscription = None
        health_sub.save()

    except HealthCheckSubscription.DoesNotExist:
        pass