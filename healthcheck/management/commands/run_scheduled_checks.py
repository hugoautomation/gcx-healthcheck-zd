from django.core.management.base import BaseCommand
from django.utils import timezone
from healthcheck.models import HealthCheckMonitoring, HealthCheckReport
from django.core.mail import send_mail
from django.template.loader import render_to_string
import requests
from zendeskapp import settings


class Command(BaseCommand):
    help = "Run scheduled health checks"

    def handle(self, *args, **options):
        now = timezone.now()
        due_checks = HealthCheckMonitoring.objects.filter(
            is_active=True, next_check__lte=now
        )

        for monitoring in due_checks:
            try:
                # Get latest report to get metadata
                latest_report = HealthCheckReport.get_latest_for_installation(
                    monitoring.installation_id
                )
                if not latest_report:
                    continue

                # Prepare API request
                url = f"https://{monitoring.subdomain}.zendesk.com"
                api_payload = {
                    "url": url,
                    "email": latest_report.raw_response.get("admin_email"),
                    "api_token": latest_report.raw_response.get("api_token"),
                    "status": "active",
                }

                # Make API request
                response = requests.post(
                    "https://app.configly.io/api/health-check/",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Token": settings.HEALTHCHECK_TOKEN,
                    },
                    json=api_payload,
                )

                if response.status_code == 200:
                    response_data = response.json()
                    
                    # Create new report
                    report = HealthCheckReport.objects.create(
                        installation_id=monitoring.installation_id,
                        instance_guid=monitoring.instance_guid,
                        subdomain=monitoring.subdomain,
                        plan=latest_report.plan,
                        app_guid=latest_report.app_guid,
                        version=latest_report.version,
                        raw_response=response_data,
                    )

                    # Send email notification
                    if monitoring.notification_emails:
                        # Prepare email context
                        issues = response_data.get("issues", [])
                        context = {
                            "subdomain": monitoring.subdomain,
                            "total_issues": len(issues),
                            "critical_issues": sum(1 for issue in issues 
                                                if issue.get("type") == "error"),
                            "warning_issues": sum(1 for issue in issues 
                                               if issue.get("type") == "warning"),
                            "report_url": f"{settings.APP_URL}/report/{report.id}/"
                        }

                        # Render email template
                        html_content = render_to_string(
                            "healthcheck/email/monitoring_report.html",
                            context
                        )

                        # Send email
                        send_mail(
                            subject=f"Zendesk Healthcheck Report for {monitoring.subdomain}",
                            message="Please view this email in HTML format",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=monitoring.notification_emails,
                            html_message=html_content,
                        )

                    # Update next check date
                    monitoring.last_check = now
                    monitoring.schedule_next_check()
                    monitoring.save()

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully completed health check for {monitoring.subdomain}"
                        )
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing check for {monitoring.subdomain}: {str(e)}"
                    )
                )