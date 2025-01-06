from django.core.cache import cache
from django.conf import settings
from .models import ZendeskUser, HealthCheckReport, HealthCheckMonitoring
from .utils import format_response_data, render_report_components
import logging

logger = logging.getLogger(__name__)


def invalidate_app_cache(installation_id):
    """Simple function to invalidate app-related caches"""
    cache_key = f'app_header:{installation_id}'
    cache.delete(cache_key)
    logger.info(f"Invalidated app cache for installation: {installation_id}")


class HealthCheckCache:
    # Cache timeouts (in seconds)
    TIMEOUTS = {
        'url_params': 300,        # 5 minutes
        'user_info': 600,         # 10 minutes
        'subscription': 300,       # 5 minutes
        'latest_report': 300,     # 5 minutes
        'historical_reports': 300, # 5 minutes
        'billing_info': 300,  # 5 minutes
        'report_results': 300,    # 5 minutes
        'report_csv': 3600,      # 1 hour
        'price_info': 3600,       # 1 hour
        'report_details': 300,    # 5 minutes
        'monitoring': 300,        # 5 minutes
        'formatted_report': 300,  # 5 minutes
        'report_unlock_status': 60, # 1 minute for unlock status
        'zaf_data': 300, # 5 minutes

    }
    @classmethod
    def get_zaf_data(cls, user_id):
        """Get cached ZAF client data"""
        cache_key = cls.get_cache_key('zaf_data', user_id)
        return cache.get(cache_key)

    @classmethod
    def set_zaf_data(cls, user_id, data):
        """Cache ZAF client data"""
        cache_key = cls.get_cache_key('zaf_data', user_id)
        cache.set(cache_key, data, cls.TIMEOUTS['zaf_data'])

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
    def get_report_results(cls, report_id, subscription_active=False):
        """Cache and retrieve formatted report results"""
        cache_key = cls.get_cache_key('report_results', f"{report_id}:{subscription_active}")
        
        cached_results = cache.get(cache_key)
        if cached_results:
            return cached_results

        try:
            report = HealthCheckReport.objects.get(id=report_id)
            formatted_data = format_response_data(
                report.raw_response,
                subscription_active=subscription_active,
                report_id=report.id,
                last_check=report.created_at,
                is_unlocked=report.is_unlocked,
            )
            results_html = render_report_components(formatted_data)
            
            cache.set(cache_key, results_html, cls.TIMEOUTS['report_results'])
            return results_html
        except HealthCheckReport.DoesNotExist:
            return None

    @classmethod
    def get_report_csv_data(cls, report_id):
        """Cache and retrieve CSV export data"""
        cache_key = cls.get_cache_key('report_csv', report_id)
        
        cached_csv = cache.get(cache_key)
        if cached_csv:
            return cached_csv

        try:
            report = HealthCheckReport.objects.get(id=report_id)
            csv_data = []
            for issue in report.raw_response.get("issues", []):
                csv_data.append([
                    issue.get("item_type", ""),
                    issue.get("type", ""),
                    issue.get("item_type", ""),
                    issue.get("message", ""),
                    issue.get("zendesk_url", ""),
                ])
            
            cache.set(cache_key, csv_data, cls.TIMEOUTS['report_csv'])
            return csv_data
        except HealthCheckReport.DoesNotExist:
            return None
    
    @classmethod
    def get_report_unlock_status(cls, report_id):
        """Cache and retrieve report unlock status"""
        cache_key = cls.get_cache_key('report_unlock_status', report_id)
        
        cached_status = cache.get(cache_key)
        if cached_status is not None:  # Check for None specifically as False is valid
            return cached_status

        try:
            report = HealthCheckReport.objects.get(id=report_id)
            status = report.is_unlocked
            cache.set(cache_key, status, cls.TIMEOUTS['report_unlock_status'])
            return status
        except HealthCheckReport.DoesNotExist:
            return None


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
    
    @classmethod
    def get_formatted_report(cls, report, subscription_active):
        """Cache and retrieve formatted report data"""
        cache_key = cls.get_cache_key('formatted_report', f"{report.id}:{subscription_active}")
        
        cached_format = cache.get(cache_key)
        if cached_format:
            return cached_format

        formatted_data = format_response_data(
            report.raw_response,
            subscription_active=subscription_active,
            report_id=report.id,
            last_check=report.created_at,
            is_unlocked=report.is_unlocked,
        )
        cache.set(cache_key, formatted_data, cls.TIMEOUTS['report_details'])
        return formatted_data
        
    @classmethod
    def get_monitoring_settings(cls, installation_id):
        """Cache and retrieve monitoring settings"""
        cache_key = cls.get_cache_key('monitoring_settings', installation_id)
        
        cached_settings = cache.get(cache_key)
        if cached_settings:
            return cached_settings

        try:
            settings = HealthCheckMonitoring.objects.get(installation_id=installation_id)
            monitoring_data = {
                'is_active': settings.is_active,
                'frequency': settings.frequency,
                'notification_emails': settings.notification_emails,
                'last_check': settings.last_check,
            }
            cache.set(cache_key, monitoring_data, cls.TIMEOUTS['monitoring'])
            return monitoring_data
        except HealthCheckMonitoring.DoesNotExist:
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
    def invalidate_report_data(cls, report_id, subscription_active=False):
        """Invalidate all caches related to a report"""
        keys_to_delete = [
            cls.get_cache_key('report_results', f"{report_id}:{subscription_active}"),
            cls.get_cache_key('report_csv', report_id),
            cls.get_cache_key('report_unlock_status', report_id),
        ]
        cache.delete_many(keys_to_delete)
        logger.info(f"Invalidated all caches for report: {report_id}")
    @classmethod
    def invalidate_monitoring_cache(cls, installation_id):
        """Invalidate monitoring settings cache"""
        keys_to_delete = [
            cls.get_cache_key('monitoring_settings', installation_id),
        ]
        cache.delete_many(keys_to_delete)
        logger.info(f"Invalidated monitoring cache for installation: {installation_id}")

    @classmethod
    def clear_all_cache(cls):
        """Clear entire cache (use with caution)"""
        cache.clear()
        logger.warning("Cleared entire cache")