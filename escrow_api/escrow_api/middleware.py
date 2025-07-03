import logging
from django.utils import timezone

logger = logging.getLogger('audit')

class UserActivityLoggingMiddleWare:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = request.user if request.user.is_authenticated else "Anonymous"
        method = request.method
        path = request.get_full_path()
        ip = self.get_client_ip(request)
        timestamp = timezone.now().isoformat()

        logger.info(f"[{timestamp}] {user} - {method} {path} - IP: {ip}")

        return response
    
    def get_client_ip(self, request):
        X_forwarded_for = request.META.get('HHTP_x_FORWARDED_FOR')
        if X_forwarded_for:
            return X_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')