from django.utils.deprecation import MiddlewareMixin

class AllowIframeMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response["X-Frame-Options"] = "ALLOWALL"
        return response