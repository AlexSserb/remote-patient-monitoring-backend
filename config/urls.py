"""URL-конфигурация проекта."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/users/", include("apps.users.urls")),
    path("api/chats/", include("apps.chats.urls")),
    path("api/diagnoses/", include("apps.diagnoses.urls")),
]
