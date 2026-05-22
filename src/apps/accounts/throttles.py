from rest_framework.throttling import SimpleRateThrottle

class EmailRateThrottle(SimpleRateThrottle):
    scope = 'email'
    
    def get_cache_key(self, request, view):
        email = request.data.get('email')

        if not email:
            return None
        
        ident = email.lower().strip()

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }