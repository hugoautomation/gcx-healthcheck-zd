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
        'historical_reports': 300, # 5 minutes
        'billing_info': 300,      # 5 minutes
        'price_info': 3600,       # 1 hour (prices don't change often)
        'report_details': 300,    # 5 minutes
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
    def get_billing_info(cls, user_id, subdomain):
        """Cache and retrieve billing information"""
        cache_key = cls.get_cache_key('billing_info', f"{subdomain}:{user_id}")
        
        cached_billing = cache.get(cache_key)
        if cached_billing:
            return cached_billing

        billing_info = {
            'subscription': cls.get_subscription_status(subdomain),
            'price_info': cls.get_price_info(),
        }
        cache.set(cache_key, billing_info, cls.TIMEOUTS['billing_info'])
        return billing_info

    @classmethod
    def get_price_info(cls):
        """Cache and retrieve price information"""
        cache_key = cls.get_cache_key('price_info', 'global')
        
        cached_prices = cache.get(cache_key)
        if cached_prices:
            return cached_prices

        prices = {
            'monthly': settings.STRIPE_PRICE_MONTHLY,
            'yearly': settings.STRIPE_PRICE_YEARLY,
        }
        cache.set(cache_key, prices, cls.TIMEOUTS['price_info'])
        return prices

    @classmethod
    def get_report_details(cls, report_id):
        """Cache and retrieve detailed report information"""
        cache_key = cls.get_cache_key('report_details', report_id)
        
        cached_details = cache.get(cache_key)
        if cached_details:
            return cached_details

        try:
            report = HealthCheckReport.objects.get(id=report_id)
            details = {
                'raw_response': report.raw_response,
                'created_at': report.created_at,
                'is_unlocked': report.is_unlocked,
                'installation_id': report.installation_id,
            }
            cache.set(cache_key, details, cls.TIMEOUTS['report_details'])
            return details
        except HealthCheckReport.DoesNotExist:
            logger.error(f"Report not found: {report_id}")
            return None

    # Cache invalidation methods
    @classmethod
    def invalidate_all_installation_data(cls, installation_id):
        """Invalidate all cache entries related to an installation"""
        keys_to_delete = [
            cls.get_cache_key('url_params', installation_id),
            cls.get_cache_key('latest_report', installation_id),
            cls.get_cache_key('historical_reports', installation_id),
        ]
        # Also invalidate related reports
        reports = HealthCheckReport.objects.filter(installation_id=installation_id)
        for report in reports:
            keys_to_delete.append(cls.get_cache_key('report_details', report.id))
        
        cache.delete_many(keys_to_delete)
        logger.info(f"Invalidated all cache for installation: {installation_id}")

    @classmethod
    def invalidate_subscription_data(cls, user_id, subdomain):
        """Invalidate all subscription-related cache entries"""
        keys_to_delete = [
            cls.get_cache_key('subscription', subdomain),
            cls.get_cache_key('billing_info', f"{subdomain}:{user_id}"),
            cls.get_cache_key('user_info', user_id),
        ]
        cache.delete_many(keys_to_delete)
        logger.info(f"Invalidated subscription cache for user: {user_id}")

    @classmethod
    def invalidate_report_cache(cls, report_id, installation_id):
        """Invalidate cache when a report is updated"""
        keys_to_delete = [
            cls.get_cache_key('report_details', report_id),
            cls.get_cache_key('latest_report', installation_id),
            cls.get_cache_key('historical_reports', installation_id),
        ]
        cache.delete_many(keys_to_delete)
        logger.info(f"Invalidated cache for report: {report_id}")

    @classmethod
    def refresh_all_cache(cls, installation_id, user_id, subdomain):
        """Force refresh all cache entries"""
        # Clear existing cache
        cls.invalidate_all_installation_data(installation_id)
        cls.invalidate_subscription_data(user_id, subdomain)
        
        # Rebuild cache
        cls.get_url_params(installation_id, None, None, user_id)
        cls.get_user_info(user_id)
        cls.get_subscription_status(subdomain)
        cls.get_latest_report(installation_id)
        cls.get_historical_reports(installation_id)
        cls.get_billing_info(user_id, subdomain)
        cls.get_price_info()
        
        logger.info(f"Refreshed all cache for installation: {installation_id}")

    @classmethod
    def clear_all_cache(cls):
        """Clear entire cache (use with caution)"""
        cache.clear()
        logger.warning("Cleared entire cache")