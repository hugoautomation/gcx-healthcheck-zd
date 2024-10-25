from django.utils.deprecation import MiddlewareMixin

class AllowIframeMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response["X-Frame-Options"] = "ALLOW-FROM https://congravitycx1714632791.zendesk.com"
        return response