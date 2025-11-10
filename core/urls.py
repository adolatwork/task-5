from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def index(request):
    return JsonResponse({"detail": "Healthy!"})


urlpatterns = [
    path("", index),
    path("health/", index),
    path("admin/", admin.site.urls),
]

apps_urlpatterns = [
    path("api/v1/", include([
        path("auth/", include("apps.user.urls")),
        path("", include("apps.order.urls")),
    ]))
]

urlpatterns += apps_urlpatterns

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns += [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path(
        "docs/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

urlpatterns += static(
    settings.STATIC_URL, document_root=settings.STATIC_ROOT
)
urlpatterns += static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)
