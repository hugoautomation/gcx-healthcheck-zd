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
                "email": latest_report.admin_email,  # Use credentials from latest report
                "api_token": latest_report.api_token,
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

                    # 1. Create new report first
                    report = HealthCheckReport.objects.create(
                        installation_id=monitoring.installation_id,
                        instance_guid=monitoring.instance_guid,
                        subdomain=monitoring.subdomain,
                        admin_email=latest_report.admin_email,  # Copy credentials
                        api_token=latest_report.api_token,      # from latest report
                        plan=latest_report.plan,
                        app_guid=latest_report.app_guid,
                        version=latest_report.version,
                        raw_response=response_data,
                    )

                    # 2. Send email notification if emails are configured
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

                        # Render and send email
                        html_content = render_to_string(
                            "healthcheck/email/monitoring_report.html", context
                        )

                        send_mail(
                            subject=f"Zendesk Healthcheck Report for {monitoring.subdomain}",
                            message="Please view this email in HTML format",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=monitoring.notification_emails,
                            html_message=html_content,
                        )
                        print(f"Email sent to {monitoring.notification_emails}")

                    # 3. Update monitoring schedule
                        monitoring.last_check = now
                    monitoring.save()  # Save to ensure last_check is persisted
                    
                    # Calculate next check based on frequency
                    if monitoring.frequency == "daily":
                        monitoring.next_check = now + timedelta(seconds=15)
                    elif monitoring.frequency == "weekly":
                        monitoring.next_check = now + timedelta(weeks=1)
                    else:  # monthly
                        monitoring.next_check = now + relativedelta(months=1)
                    
                    monitoring.save()

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
