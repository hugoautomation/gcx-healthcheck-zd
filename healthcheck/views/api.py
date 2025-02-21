from django.http import JsonResponse
from ..models import SiteConfiguration

def get_chat_widget(request):
    config = SiteConfiguration.objects.first()
    return JsonResponse({
        'is_enabled': bool(config and config.is_chat_enabled),
        'script': config.chat_widget_script if config and config.is_chat_enabled else ''
    }) 