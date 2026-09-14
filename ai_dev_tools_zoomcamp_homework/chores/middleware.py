from django.contrib.auth import logout
from django.contrib.sessions.middleware import SessionMiddleware


class ActivitySessionMiddleware(SessionMiddleware):
    def process_response(self, request, response):
        # Passive live refreshes must not keep an unattended browser logged in.
        if request.headers.get("X-Live-Refresh") == "1":
            return response
        return super().process_response(request, response)


class PINSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and "pin_session_version" in request.session:
            if request.session["pin_session_version"] != request.user.session_version or request.user.locked_at:
                logout(request)
        return self.get_response(request)
