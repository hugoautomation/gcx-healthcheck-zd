from django.urls import path
from .views import (
    # App views
    app,
    create_or_update_user,
    # Billing views
    billing_page,
    create_checkout_session,
    create_payment_intent,
    # Monitoring views
    monitoring,
    monitoring_settings,
    # Healthcheck views
    health_check,
    download_report_csv,
    check_unlock_status,
    get_historical_report,
    check_task_status,
)

# from . import views
from . import success_page
from . import cache_views

urlpatterns = [
    path(
        "test/subscription-success/",
        success_page.test_subscription_success,
        name="test_subscription_success",
    ),
    path(
        "test/one-off-success/",
        success_page.test_one_off_success,
        name="test_one_off_success",
    ),
    path("", app, name="app"),
    path("health_check/", health_check, name="health_check"),
    path('health_check/status/<str:task_id>/', check_task_status, name='check_task_status'),  # Add this line
    path(
        "report/<int:report_id>/download/",
        download_report_csv,
        name="download_report_csv",
    ),
    path(
        "payment/subscription/success/",
        success_page.subscription_success,
        name="subscription_success",
    ),
    path(
        "payment/one-off/success/", success_page.one_off_success, name="one_off_success"
    ),
    path(
        "report/<int:report_id>/",
        get_historical_report,
        name="get_historical_report",
    ),
    path("check-unlock-status/", check_unlock_status, name="check_unlock_status"),
    path("monitoring-settings/", monitoring_settings, name="monitoring_settings"),
    path("monitoring/", monitoring, name="monitoring"),
    path(
        "api/users/create-or-update/",
        create_or_update_user,
        name="create_or_update_user",
    ),
    path("billing/", billing_page, name="billing"),  # Add this line
    path(
        "create-checkout-session/",
        create_checkout_session,
        name="create_checkout_session",
    ),
    path(
        "create-payment-intent/",
        create_payment_intent,
        name="create_payment_intent",
    ),
    path("api/cache/zaf-data/", cache_views.cache_zaf_data, name="cache_zaf_data"),
    path(
        "api/cache/zaf-data/",
        cache_views.get_cached_zaf_data,
        name="get_cached_zaf_data",
    ),
]
