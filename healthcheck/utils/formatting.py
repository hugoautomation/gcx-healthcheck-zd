from django.utils.timesince import timesince


def format_response_data(
    response_data,
    subscription_active=False,
    report_id=None,
    last_check=None,
    is_unlocked=False,
):
    """
    Helper function to format response data consistently
    Shows full data if either:
    - Has active subscription
    - Report is unlocked via one-off payment
    """
    issues = response_data.get("issues", [])
    counts = response_data.get("counts", {})
    total_counts = response_data.get("sum_totals", {})
    has_status_values = any('active' in issue for issue in issues)

    # Calculate hidden issues for users without access
    hidden_issues_count = 0
    hidden_categories = {}

    # Filter issues if user has no access (neither subscription nor one-off unlock)
    if not subscription_active and not is_unlocked and report_id:
        # Count issues by category before filtering
        for issue in issues:
            item_type = issue.get("item_type")
            if item_type not in ["TicketForms", "TicketFields"]:
                hidden_categories[item_type] = hidden_categories.get(item_type, 0) + 1
                hidden_issues_count += 1

        # Show only Ticket Forms and Fields issues for users without access
        issues = [
            issue
            for issue in issues
            if issue.get("item_type") in ["TicketForms", "TicketFields"]
        ]

    return {
        "has_status_values": has_status_values,
        "instance": {
            "name": response_data.get("name", "Unknown"),
            "url": response_data.get("instance_url", "Unknown"),
            "admin_email": response_data.get("admin_email", "Unknown"),
            "created_at": response_data.get("created_at", "Unknown"),
        },
        "report_created_at": last_check.strftime("%d %b %Y")
        if last_check
        else None,  # Add report creation date
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
        "is_unlocked": True
        if subscription_active
        else is_unlocked,  # This is the key change
        "report_id": report_id,
        "issues": [
            {
                "category": issue.get("item_type", "Unknown"),
                "severity": issue.get("type", "warning"),
                "active": issue.get("active", False),
                "description": issue.get("message", ""),
                "zendesk_url": issue.get("zendesk_url", "#"),
            }
            for issue in issues
        ],
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
