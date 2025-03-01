from django.core.management.base import BaseCommand
from django.utils import timezone
from healthcheck.models import HealthCheckMonitoring, HealthCheckReport
from django.core.mail import send_mail
from django.template.loader import render_to_string
import requests
from zendeskapp import settings
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class Command(BaseCommand):
    help = "Run scheduled health checks"

    def handle(self, *args, **options):
        now = timezone.now()
        due_checks = HealthCheckMonitoring.objects.filter(
            is_active=True, next_check__lte=now
        )

        self.stdout.write(f"Found {due_checks.count()} checks due for processing")

        for monitoring in due_checks:
            try:
                # Get latest report to get metadata
                latest_report = HealthCheckReport.get_latest_for_installation(
                    monitoring.installation_id
                )
                if not latest_report:
                    self.stdout.write(
                        f"No latest report found for {monitoring.installation_id}"
                    )
                    continue

                # Update last_check and calculate next_check before making the API call
                monitoring.last_check = now

                # Calculate next check based on frequency
                if monitoring.frequency == "daily":
                    monitoring.next_check = now + timedelta(days=1)
                elif monitoring.frequency == "weekly":
                    monitoring.next_check = now + timedelta(weeks=1)
                else:  # monthly
                    monitoring.next_check = now + relativedelta(months=1)

                monitoring.save()

                self.stdout.write(
                    f"Updated next check for {monitoring.subdomain} to {monitoring.next_check}"
                )

                # Make API request
                response = requests.post(
                    "https://app.configly.io/api/health-check/",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Token": settings.HEALTHCHECK_TOKEN,
                    },
                    json={
                        "url": f"https://{monitoring.subdomain}.zendesk.com",
                        "email": latest_report.admin_email,
                        "api_token": latest_report.api_token,
                        "status": "active",
                    },
                )

                if response.status_code == 200:
                    response_data = response.json()

                    # Create new report
                    report = HealthCheckReport.objects.create(
                        installation_id=monitoring.installation_id,
                        instance_guid=monitoring.instance_guid,
                        subdomain=monitoring.subdomain,
                        admin_email=latest_report.admin_email,
                        api_token=latest_report.api_token,
                        app_guid=latest_report.app_guid,
                        version=latest_report.version,
                        raw_response=response_data,
                    )

                    # Send email notification if configured
                    if monitoring.notification_emails:
                        issues = response_data.get("issues", [])
                        context = {
                            "subdomain": monitoring.subdomain,
                            "total_issues": len(issues),
                            "critical_issues": sum(
                                1 for issue in issues if issue.get("type") == "error"
                            ),
                            "warning_issues": sum(
                                1 for issue in issues if issue.get("type") == "warning"
                            ),
                            "report_url": f"{settings.APP_URL}/report/{report.id}/",
                        }

                        send_mail(
                            subject=f"Zendesk Healthcheck Report: {monitoring.subdomain}",
                            message="Please view this email in HTML format",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=monitoring.notification_emails,
                            html_message=render_to_string(
                                "healthcheck/email/monitoring_report.html", context
                            ),
                        )
                        self.stdout.write(
                            f"Email sent to {monitoring.notification_emails}"
                        )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully completed health check for {monitoring.subdomain}. Next check scheduled for {monitoring.next_check}"
                        )
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing check for {monitoring.subdomain}: {str(e)}"
                    )
                )
