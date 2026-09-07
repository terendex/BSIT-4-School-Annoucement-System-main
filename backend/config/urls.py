from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    """Render pings this to keep the service warm and to verify deploys."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", healthcheck, name="healthz"),
    path("django-admin/", admin.site.urls),
    path("api/", include("announcements.urls")),
]

# Local-dev only: serve uploads from disk when Cloudinary is not configured.
if settings.DEBUG and not settings.CLOUDINARY_ENABLED:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
