from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from django.core.cache import cache
from .cache_utils import HealthCheckCache
import logging

logger = logging.getLogger(__name__)



@csrf_exempt
@require_http_methods(["POST"])
def cache_zaf_data(request):
    """Cache ZAF client data"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({"error": "Missing user_id"}, status=400)

        # Cache the ZAF data
        cache_key = HealthCheckCache.get_cache_key('zaf_data', user_id)
        cache.set(cache_key, {
            'metadata': data.get('metadata'),
            'context': data.get('context'),
            'user_info': data.get('user_info')
        }, timeout=300)  # 5 minutes

        return JsonResponse({"success": True})
    except Exception as e:
        logger.error(f"Error caching ZAF data: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_cached_zaf_data(request):
    """Retrieve cached ZAF client data"""
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({"error": "Missing user_id"}, status=400)

    cache_key = HealthCheckCache.get_cache_key('zaf_data', user_id)
    cached_data = cache.get(cache_key)

    if cached_data:
        return JsonResponse(cached_data)
    return JsonResponse({"error": "No cached data found"}, status=404)