from django.core.cache import cache
from django.conf import settings
from .models import ZendeskUser, HealthCheckReport
import logging

logger = logging.getLogger(__name__)

class HealthCheckCache:
    # Cache timeouts (in seconds)
    TIMEOUTS = {
        'url_params': 300,        # 5 minutes
        'user_info': 600,         # 10 minutes
        'subscription': 300,       # 5 minutes
        'latest_report': 300,     # 5 minutes
        'historical_reports': 300  # 5 minutes
    }

    @staticmethod
    def get_cache_key(key_type, identifier):
        """Generate a cache key based on type and identifier"""
        return f"healthcheck:{key_type}:{identifier}"

    @classmethod
    def get_url_params(cls, installation_id, app_guid, origin, user_id):
        """Cache and retrieve URL parameters"""
        cache_key = cls.get_cache_key('url_params', installation_id)
        
        cached_params = cache.get(cache_key)
        if cached_params:
            return cached_params

        params = {
            'installation_id': installation_id,
            'app_guid': app_guid,
            'origin': origin,
            'user_id': user_id
        }
        cache.set(cache_key, params, cls.TIMEOUTS['url_params'])
        return params

    @classmethod
    def get_user_info(cls, user_id):
        """Cache and retrieve user information"""
        cache_key = cls.get_cache_key('user_info', user_id)
        
        cached_user = cache.get(cache_key)
        if cached_user:
            return cached_user

        try:
            user = ZendeskUser.objects.get(user_id=user_id)
            cache.set(cache_key, user, cls.TIMEOUTS['user_info'])
            return user
        except ZendeskUser.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return None

    @classmethod
    def get_subscription_status(cls, subdomain):
        """Cache and retrieve subscription status"""
        cache_key = cls.get_cache_key('subscription', subdomain)
        
        cached_status = cache.get(cache_key)
        if cached_status:
            return cached_status

        status = ZendeskUser.get_subscription_status(subdomain)
        cache.set(cache_key, status, cls.TIMEOUTS['subscription'])
        return status

    @classmethod
    def get_latest_report(cls, installation_id):
        """Cache and retrieve latest health check report"""
        cache_key = cls.get_cache_key('latest_report', installation_id)
        
        cached_report = cache.get(cache_key)
        if cached_report:
            return cached_report

        report = HealthCheckReport.get_latest_for_installation(installation_id)
        if report:
            cache.set(cache_key, report, cls.TIMEOUTS['latest_report'])
        return report

    @classmethod
    def get_historical_reports(cls, installation_id, limit=10):
        """Cache and retrieve historical reports"""
        cache_key = cls.get_cache_key('historical_reports', installation_id)
        
        cached_reports = cache.get(cache_key)
        if cached_reports:
            return cached_reports

        reports = HealthCheckReport.objects.filter(
            installation_id=installation_id
        ).order_by("-created_at")[:limit]
        
        cache.set(cache_key, list(reports), cls.TIMEOUTS['historical_reports'])
        return reports

    @classmethod
    def invalidate_installation_cache(cls, installation_id):
        """Invalidate all cache entries for an installation"""
        keys_to_delete = [
            cls.get_cache_key('url_params', installation_id),
            cls.get_cache_key('latest_report', installation_id),
            cls.get_cache_key('historical_reports', installation_id)
        ]
        cache.delete_many(keys_to_delete)

    @classmethod
    def invalidate_user_cache(cls, user_id, subdomain):
        """Invalidate all cache entries for a user"""
        keys_to_delete = [
            cls.get_cache_key('user_info', user_id),
            cls.get_cache_key('subscription', subdomain)
        ]
        cache.delete_many(keys_to_delete)