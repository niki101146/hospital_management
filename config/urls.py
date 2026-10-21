from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    # The admin area is the Website Manager at /panel/. Old /admin/ links are sent there.
    path("admin/", RedirectView.as_view(pattern_name="panel_home", permanent=False)),
    # Django's built-in admin is kept only as a hidden backup.
    path("django-admin/", admin.site.urls),
    path("", include("hms.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
