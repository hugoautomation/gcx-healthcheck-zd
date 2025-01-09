from django.template.loader import render_to_string


def render_report_components(formatted_data):
    """Helper function to render report template"""
    # If it's an error message, don't nest it under 'data'
    if "error" in formatted_data and len(formatted_data) == 1:
        return render_to_string("healthcheck/results.html", formatted_data)
    # Otherwise, wrap it in 'data' as before
    return render_to_string("healthcheck/results.html", {"data": formatted_data})
