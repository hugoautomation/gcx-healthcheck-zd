from django.urls import path
from . import views

urlpatterns = [
    path('', views.app, name='app'),
    path('check/', views.health_check, name='health_check'),
    path('latest_report/', views.get_latest_report, name='get_latest_report'),
]
