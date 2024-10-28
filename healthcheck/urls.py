from django.urls import path
from . import views

urlpatterns = [
    path("", views.app, name="app"),
    path("check/", views.health_check, name="health_check"),
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("check-unlock-status/", views.check_unlock_status, name="check_unlock_status"),
]
