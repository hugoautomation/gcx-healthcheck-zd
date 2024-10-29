from django.template.loader import render_to_string
from .models import HealthCheckReport, HealthCheckMonitoring
from django.utils.timesince import timesince


def format_response_data(response_data, plan="Free", report_id=None, last_check=None):
    """Helper function to format response data consistently"""
    issues = response_data.get("issues", [])
    counts = response_data.get("counts", {})
    total_counts = response_data.get("sum_totals", {})

    # Calculate hidden issues for free plan
    hidden_issues_count = 0
    hidden_categories = {}

    if plan == "Free" and report_id:
        try:
            report = HealthCheckReport.objects.get(id=report_id)
            is_unlocked = report.is_unlocked
        except HealthCheckReport.DoesNotExist:
            is_unlocked = False

        if not is_unlocked:
            # Count issues by category before filtering
            for issue in issues:
                category = issue.get("item_type")
                if category not in ["ticket_forms", "ticket_fields"]:
                    hidden_issues_count += 1
                    hidden_categories[category] = hidden_categories.get(category, 0) + 1

            # Filter issues for display
            issues = [
                issue
                for issue in issues
                if issue.get("item_type") in ["ticket_forms", "ticket_fields"]
            ]

    return {
        "instance": {
            "name": response_data.get("name", "Unknown"),
            "url": response_data.get("instance_url", "Unknown"),
            "admin_email": response_data.get("admin_email", "Unknown"),
            "created_at": response_data.get("created_at", "Unknown"),
        },
        "last_check": last_check.strftime("%Y-%m-%d %H:%M:%S") if last_check else None,
        "time_since_check": timesince(last_check) if last_check else "Never",
        "total_issues": len(issues),
        "critical_issues": sum(1 for issue in issues if issue.get("type") == "error"),
        "warning_issues": sum(1 for issue in issues if issue.get("type") == "warning"),
        "counts": {
            "ticket_fields": counts.get("ticket_fields", {}),
            "user_fields": counts.get("user_fields", {}),
            "organization_fields": counts.get("organization_fields", {}),
            "ticket_forms": counts.get("ticket_forms", {}),
            "triggers": counts.get("ticket_triggers", {}),
            "macros": counts.get("macros", {}),
            "users": counts.get("zendesk_users", {}),
            "sla_policies": counts.get("sla_policies", {}),
        },
        "totals": {
            "total": total_counts.get("sum_total", 0),
            "draft": total_counts.get("sum_draft", 0),
            "published": total_counts.get("sum_published", 0),
            "changed": total_counts.get("sum_changed", 0),
            "deletion": total_counts.get("sum_deletion", 0),
            "total_changes": total_counts.get("sum_total_changes", 0),
        },
        "categories": sorted(
            set(issue.get("item_type", "Unknown") for issue in issues)
        ),
        "hidden_issues_count": hidden_issues_count,
        "hidden_categories": hidden_categories,
        "is_free_plan": plan == "Free",
        "is_unlocked": is_unlocked if plan == "Free" else True,
        "report_id": report_id,
        "issues": [
            {
                "category": issue.get("item_type", "Unknown"),
                "severity": issue.get("type", "warning"),
                "description": issue.get("message", ""),
                "zendesk_url": issue.get("zendesk_url", "#"),
            }
            for issue in issues
        ],
    }


def get_monitoring_context(installation_id, client_plan, latest_report=None):
    """Helper function to get monitoring settings context"""
    is_free_plan = client_plan == "Free"

    try:
        monitoring = HealthCheckMonitoring.objects.get(installation_id=installation_id)
        monitoring_data = {
            "is_active": monitoring.is_active and not is_free_plan,
            "frequency": monitoring.frequency,
            "notification_emails": monitoring.notification_emails or [],
            "instance_guid": monitoring.instance_guid,
            "subdomain": monitoring.subdomain,
        }
    except HealthCheckMonitoring.DoesNotExist:
        monitoring_data = {
            "is_active": False,
            "frequency": "weekly",
            "notification_emails": [],
            "instance_guid": latest_report.instance_guid if latest_report else "",
            "subdomain": latest_report.subdomain if latest_report else "",
        }

    # Return monitoring settings separately from report data
    return {
        "monitoring_settings": monitoring_data,
        "is_free_plan": is_free_plan,
    }


def format_historical_reports(reports):
    """Helper function to format historical reports for display"""
    return [
        {
            "id": report.id,
            "created_at": report.created_at.strftime("%d %b %Y"),
            "is_unlocked": report.is_unlocked,
            "total_issues": len(report.raw_response.get("issues", [])),
        }
        for report in reports
    ]


def render_report_components(formatted_data):
    """Helper function to render report template"""
    # If it's an error message, don't nest it under 'data'
    if 'error' in formatted_data and len(formatted_data) == 1:
        return render_to_string("healthcheck/results.html", formatted_data)
    # Otherwise, wrap it in 'data' as before
    return render_to_string("healthcheck/results.html", {"data": formatted_data})
