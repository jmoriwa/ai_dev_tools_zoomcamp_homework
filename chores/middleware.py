from django.contrib.auth import logout


class PINSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and "pin_session_version" in request.session:
            if request.session["pin_session_version"] != request.user.session_version or request.user.locked_at:
                logout(request)
        return self.get_response(request)
