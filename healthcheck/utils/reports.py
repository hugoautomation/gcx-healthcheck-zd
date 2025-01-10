from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)


def render_report_components(formatted_data):
    """Helper function to render report template"""
    try:
        # If it's an error message, don't nest it under 'data'
        if "error" in formatted_data and len(formatted_data) == 1:
            return render_to_string("healthcheck/results.html", formatted_data)

        # Ensure report_id is available in the context
        context = {
            "data": formatted_data,
            "report_id": formatted_data.get("report_id"),  # Make sure this is passed
        }
        return render_to_string("healthcheck/results.html", context)
    except Exception as e:
        logger.error(f"Error rendering report template: {str(e)}")
        return render_to_string(
            "healthcheck/results.html", {"error": "Error rendering report template"}
        )
