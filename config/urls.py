from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as media_serve
from django.views.generic import RedirectView

urlpatterns = [
    # The admin area is the Website Manager at /panel/. Old /admin/ links are sent there.
    path("admin/", RedirectView.as_view(pattern_name="panel_home", permanent=False)),
    # Django's built-in admin is kept only as a hidden backup.
    path("django-admin/", admin.site.urls),
    # Uploaded photos/banners. Works with DEBUG off too (fine for a small hospital site).
    re_path(r"^media/(?P<path>.*)$", media_serve, {"document_root": settings.MEDIA_ROOT}),
    path("", include("hms.urls")),
]
