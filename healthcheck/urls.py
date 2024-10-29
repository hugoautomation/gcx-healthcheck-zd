from django.urls import path
from . import views

urlpatterns = [
    path("", views.app, name="app"),
    path("check/", views.health_check, name="health_check"),
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("check-unlock-status/", views.check_unlock_status, name="check_unlock_status"),
    path(
        "report/<int:report_id>/download/",
        views.download_report_csv,
        name="download_report_csv",
    ),
    path(
        "report/<int:report_id>/",
        views.get_historical_report,
        name="get_historical_report",
    ),
    path("monitoring-settings/", views.monitoring_settings, name="monitoring_settings"),
    path(
        "update-installation-plan/",
        views.update_installation_plan,
        name="update_installation_plan",
    ),
    path("report/latest/", views.get_latest_report, name="get_latest_report"),
]
