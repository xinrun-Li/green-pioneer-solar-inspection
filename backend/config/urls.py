from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.auth_urls")),
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/stations/", include("apps.stations.urls")),
    path("api/v1/upload-batches/", include("apps.uploads.urls")),
    path("api/v1/recognition-jobs/", include("apps.recognition.urls")),
    path("api/v1/detections/", include("apps.recognition.detection_urls")),
    path("api/v1/events/", include("apps.events.urls")),
    path("api/v1/inspections/", include("apps.inspections.urls")),
    path("api/v1/assistant/", include("apps.assistant.urls")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/", include("apps.datasets.urls")),
    path("api/v1/", include("apps.training.urls")),
    path("api/v1/", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
