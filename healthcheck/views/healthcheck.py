from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
import requests
from zendeskapp import settings
from ..models import HealthCheckReport, ZendeskUser
from ..utils.formatting import format_response_data
from ..utils.reports import render_report_components
from ..utils.stripe import get_default_subscription_status

from ..tasks import run_health_check
from ..cache_utils import HealthCheckCache, invalidate_app_cache
import logging
import csv

logger = logging.getLogger(__name__)

@csrf_exempt
def health_check(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body) if request.body else {}
            
            # Start async task
            task = run_health_check.delay(
                url=data.get("url"),
                email=data.get("email"),
                api_token=data.get("api_token"),
                installation_id=data.get("installation_id"),
                user_id=data.get("user_id"),
                subdomain=data.get("subdomain"),
                instance_guid=data.get("instance_guid"),
                app_guid=data.get("app_guid"),
                stripe_subscription_id=data.get("stripe_subscription_id"),
                version=data.get("version", "1.0.0"),
            )

            # Only return the task ID, don't send results_html
            return JsonResponse({
                "task_id": task.id,
                "status": "pending"
            })

        except Exception as e:
            logger.error(f"Error starting health check: {str(e)}")
            return JsonResponse({
                "error": True, 
                "message": f"Error processing request: {str(e)}"
            })

    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
def check_task_status(request, task_id):
    """Check the status of a health check task"""
    task = run_health_check.AsyncResult(task_id)
    
    if task.ready():
        result = task.get()
        if result.get("error"):
            return JsonResponse({
                "status": "error",
                "error": result["message"],
                "results_html": render_report_components({
                    "error": result["message"]
                })
            })
        
        try:
            report = HealthCheckReport.objects.get(id=result["report_id"])
            subscription_status = get_default_subscription_status()
            
            return JsonResponse({
                "status": "complete",
                "results_html": HealthCheckCache.get_report_results(
                    report.id, 
                    subscription_active=subscription_status["active"]
                )
            })
        except Exception as e:
            logger.error(f"Error rendering report: {str(e)}")
            return JsonResponse({
                "status": "error",
                "error": str(e)
            })
    
    # For pending tasks, only return status
    return JsonResponse({
        "status": "pending"
    })
# @csrf_exempt
# def health_check(request):
#     if request.method == "POST":
#         try:
#             subscription_status = get_default_subscription_status()
#             # Extract data from request
#             data = json.loads(request.body) if request.body else {}
#             installation_id = data.get("installation_id")
#             user_id = data.get("user_id")
#             invalidate_app_cache(installation_id)

#             logger.info(
#                 "Health check details",
#                 extra={
#                     "extra_data": json.dumps(
#                         {
#                             "installation_id": installation_id,
#                             "user_id": user_id,
#                             "data": data,
#                         }
#                     )
#                 },
#             )

#             # Get user and subscription status
#             user = ZendeskUser.objects.get(user_id=user_id)
#             if user:
#                 subscription_status = HealthCheckCache.get_subscription_status(
#                     user.subdomain
#                 )

#             analytics.track(
#                 user_id,
#                 "Health Check Started",
#                 {
#                     "subdomain": data.get("subdomain"),
#                     "email": data.get("email"),
#                     "subscription_status": subscription_status["status"],
#                     "subscription_active": subscription_status["active"],
#                 },
#             )

#             # Prepare URL
#             url = data.get("url")
#             if not url or not url.startswith("https://"):
#                 url = f"https://{url}"

#             api_url = (
#                 "https://app.configly.io/api/health-check/"
#                 if settings.ENVIRONMENT == "production"
#                 else "https://django-server-development-1b87.up.railway.app/api/health-check/"
#             )

#             # Make API request
#             api_payload = {
#                 "url": url,
#                 "email": data.get("email"),
#                 "api_token": data.get("api_token"),
#                 "status": "active",
#             }

#             logger.info(
#                 "Making API request",
#                 extra={
#                     "extra_data": json.dumps(
#                         {
#                             "api_url": api_url,
#                             "subdomain": data.get("subdomain"),
#                             "payload": api_payload,
#                         }
#                     )
#                 },
#             )

#             response = requests.post(
#                 api_url,
#                 headers={
#                     "X-API-Token": settings.HEALTHCHECK_TOKEN,
#                     "Content-Type": "application/json",
#                 },
#                 json=api_payload,
#             )

#             if response.status_code == 401:
#                 error_message = "Authentication failed. Please verify your Admin Email and API Token are correct."
#                 results_html = render_report_components(
#                     {"data": None, "error": error_message}
#                 )
#                 return JsonResponse({"error": True, "results_html": results_html})

#             if response.status_code != 200:
#                 results_html = render_report_components(
#                     {"data": None, "error": f"API Error: {response.text}"}
#                 )
#                 return JsonResponse({"error": True, "results_html": results_html})

#             # Get response data
#             response_data = response.json()

#             # Create report
#             report = HealthCheckReport.objects.create(
#                 installation_id=int(installation_id),
#                 api_token=data.get("api_token"),
#                 admin_email=data.get("email"),
#                 instance_guid=data.get("instance_guid"),
#                 subdomain=data.get("subdomain", ""),
#                 app_guid=data.get("app_guid"),
#                 stripe_subscription_id=subscription_status.get("subscription_id"),
#                 version=data.get("version", "1.0.0"),
#                 raw_response=response_data,
#             )

#             analytics.identify(
#                 user_id,
#                 {
#                     "email": user.email,
#                     "last_healthcheck": report.created_at,
#                 },
#             )
#             logger.info(f"subscription_status: {subscription_status}")

#             results_html = HealthCheckCache.get_report_results(
#                 report.id, subscription_active=subscription_status["active"]
#             )
#             analytics.track(
#                 user_id,
#                 "Health Check Completed",
#                 {
#                     "total_issues": len(response_data.get("issues", [])),
#                     "report_id": report.id,
#                     "critical_issues": sum(
#                         1
#                         for issue in response_data.get("issues", [])
#                         if issue.get("type") == "error"
#                     ),
#                     "warning_issues": sum(
#                         1
#                         for issue in response_data.get("issues", [])
#                         if issue.get("type") == "warning"
#                     ),
#                     "is_unlocked": report.is_unlocked,
#                     "subscription_status": subscription_status["status"],
#                     "subscription_active": subscription_status["active"],
#                 },
#             )
#             HealthCheckCache.invalidate_report_cache(report.id, installation_id)

#             return JsonResponse({"error": False, "results_html": results_html})

#         except Exception as e:
#             results_html = render_report_components(
#                 {"data": None, "error": f"Error processing request: {str(e)}"}
#             )
#             return JsonResponse({"error": True, "results_html": results_html})

#     return HttpResponse("Method not allowed", status=405)


@csrf_exempt
def download_report_csv(request, report_id):
    """Download health check report as CSV"""
    try:
        # Get cached CSV data
        csv_data = HealthCheckCache.get_report_csv_data(report_id)
        if not csv_data:
            # If not in cache, get from database
            report = HealthCheckReport.objects.get(id=report_id)
            csv_data = []
            for issue in report.raw_response.get("issues", []):
                csv_data.append(
                    [
                        issue.get("item_type", ""),
                        issue.get("type", ""),
                        issue.get("item_type", ""),
                        issue.get("message", ""),
                        issue.get("zendesk_url", ""),
                    ]
                )

        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="healthcheck_report_{report_id}.csv"'
        )

        # Create CSV writer
        writer = csv.writer(response)

        # Write header row
        writer.writerow(
            ["Type", "Severity", "Object Type", "Description", "Zendesk URL"]
        )

        # Write data rows from cache or database
        writer.writerows(csv_data)

        return response

    except HealthCheckReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)
    except Exception as e:
        logger.error(f"Error generating CSV for report {report_id}: {str(e)}")
        return JsonResponse({"error": "Error generating CSV"}, status=500)


@csrf_exempt
def check_unlock_status(request):
    report_id = request.GET.get("report_id")
    if not report_id:
        return JsonResponse({"error": "No report ID provided"}, status=400)

    # Get cached unlock status
    is_unlocked = HealthCheckCache.get_report_unlock_status(report_id)
    if is_unlocked is None:
        return JsonResponse({"error": "Report not found"}, status=404)

    return JsonResponse({"is_unlocked": is_unlocked, "report_id": report_id})


@csrf_exempt
def get_historical_report(request, report_id):
    """Fetch a historical report by ID"""
    try:
        subscription_status = get_default_subscription_status()
        report = HealthCheckReport.objects.get(id=report_id)

        # Get subscription status for the report's subdomain
        if report:
            subscription_status = HealthCheckCache.get_subscription_status(
                report.subdomain
            )

        # Format the report data
        report_data = format_response_data(
            report.raw_response,
            subscription_active=subscription_status["active"],
            report_id=report.id,
            last_check=report.created_at,
            is_unlocked=report.is_unlocked,
        )

        # Use render_report_components utility
        results_html = render_report_components(report_data)

        return JsonResponse({"results_html": results_html})

    except HealthCheckReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return JsonResponse({"error": "Report not found"}, status=404)
    except Exception as e:
        logger.error(f"Error fetching historical report: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
