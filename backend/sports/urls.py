from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.views.static import serve # Import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('nfl.urls')),
    # Serve static files directly from STATIC_ROOT
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

# Catch-all for SPA index.html - MUST be the last entry
urlpatterns += [
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),
]