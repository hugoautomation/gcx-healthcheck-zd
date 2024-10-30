from django.test import TestCase
from django.utils import timezone
from django.core import mail
from datetime import timedelta
from .models import HealthCheckMonitoring, HealthCheckReport
from django.core.mail import send_mail
from django.template.loader import render_to_string


class MonitoringTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test monitoring setting
        self.monitoring = HealthCheckMonitoring.objects.create(
            installation_id=12345,
            instance_guid="test-guid",
            subdomain="test-subdomain",
            is_active=True,
            frequency="daily",
            notification_emails=["test@example.com"],
            last_check=timezone.now() - timedelta(days=2)
        )

        # Create test report
        self.report = HealthCheckReport.objects.create(
            installation_id=12345,
            instance_guid="test-guid",
            app_guid="test-app-guid",
            subdomain="test-subdomain",
            plan="Premium",
            version="1.0.0",
            raw_response={
                "issues": [
                    {
                        "item_type": "ticket_forms",
                        "type": "error",
                        "message": "Test issue",
                        "zendesk_url": "https://test.zendesk.com"
                    }
                ]
            }
        )

    def test_monitoring_creation(self):
        """Test that monitoring settings are created correctly"""
        self.assertEqual(self.monitoring.installation_id, 12345)
        self.assertEqual(self.monitoring.frequency, "daily")
        self.assertEqual(self.monitoring.notification_emails, ["test@example.com"])
        self.assertTrue(self.monitoring.is_active)

    def test_next_check_scheduling(self):
        """Test that next_check is scheduled correctly"""
        self.monitoring.schedule_next_check()
        
        # For daily frequency
        if self.monitoring.frequency == "daily":
            expected_next = self.monitoring.last_check + timedelta(days=1)
        elif self.monitoring.frequency == "weekly":
            expected_next = self.monitoring.last_check + timedelta(weeks=1)
        else:  # monthly
            expected_next = self.monitoring.last_check + timedelta(days=30)  # approximate

        self.assertIsNotNone(self.monitoring.next_check)
        # Allow for small time differences in test
        time_difference = abs((self.monitoring.next_check - expected_next).total_seconds())
        self.assertTrue(time_difference < 60)  # Within 60 seconds

    def test_monitoring_email(self):
        """Test monitoring email sending"""
        context = {
            "subdomain": self.monitoring.subdomain,
            "total_issues": len(self.report.raw_response.get("issues", [])),
            "report_url": f"https://your-app-url.com/report/{self.report.id}/"
        }
        
        html_content = render_to_string("healthcheck/email/monitoring_report.html", context)
        
        send_mail(
            subject=f"Zendesk Healthcheck Report for {self.monitoring.subdomain}",
            message="Please view this email in HTML format",
            from_email="test@example.com",
            recipient_list=self.monitoring.notification_emails,
            html_message=html_content
        )

        # Test that one message has been sent
        self.assertEqual(len(mail.outbox), 1)
        
        # Test the subject
        self.assertEqual(
            mail.outbox[0].subject,
            f"Zendesk Healthcheck Report for {self.monitoring.subdomain}"
        )
        
        # Test that the recipient is correct
        self.assertEqual(mail.outbox[0].to, self.monitoring.notification_emails)

    def test_monitoring_due_check(self):
        """Test identifying monitoring settings due for check"""
        # Create another monitoring setting that's not due
        HealthCheckMonitoring.objects.create(
            installation_id=54321,
            instance_guid="test-guid-2",
            subdomain="test-subdomain-2",
            is_active=True,
            frequency="daily",
            notification_emails=["test2@example.com"],
            last_check=timezone.now(),  # Current time, so not due
            next_check=timezone.now() + timedelta(days=1)
        )

        # Query for monitoring settings due for check
        due_for_check = HealthCheckMonitoring.objects.filter(
            is_active=True,
            next_check__lte=timezone.now()
        )

        # Should only find our original monitoring setting
        self.assertEqual(due_for_check.count(), 1)
        self.assertEqual(due_for_check.first(), self.monitoring)