"""Health check that answers before Django inspects the Host header."""
from django.http import JsonResponse

HEALTH_PATHS = frozenset(["/healthz", "/healthz/"])


class HealthCheckMiddleware:
    """Serve /healthz/ at the very top of the middleware stack.

    Platform healthchecks (Railway, Render, uptime pingers) reach the container
    directly and send whatever Host header they please - Railway uses
    "healthcheck.railway.app". Anything further down the stack calls
    request.get_host(), which raises DisallowedHost for a host that is not in
    ALLOWED_HOSTS, so the probe gets a 400 and the deploy is marked unhealthy.

    Reading request.path needs no host validation, so answering here makes the
    check independent of ALLOWED_HOSTS, of SECURE_SSL_REDIRECT (this sits above
    SecurityMiddleware, so there is no redirect to follow over plain HTTP), and
    of which hostname the platform happens to use.

    It deliberately touches nothing else: no database, no session, no auth - so
    it reports "the process is up and serving", which is what a healthcheck is
    for. Deeper checks belong in a separate endpoint.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in HEALTH_PATHS:
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
