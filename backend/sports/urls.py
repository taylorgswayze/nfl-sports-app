from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.views.static import serve # Import serve
from django.http import FileResponse
import os

def serve_react_app(request):
    """Serve the React app's index.html file"""
    index_path = os.path.join(settings.STATIC_ROOT, 'index.html')
    return FileResponse(open(index_path, 'rb'), content_type='text/html')

from nfl import auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('nfl.urls')),
    # Google's console registers the redirect URI without the /api prefix;
    # both spellings resolve here so the console entry and the API stay in
    # step (exact-match rules, trailing slash included).
    path('auth/callback', auth_views.callback),
    path('auth/callback/', auth_views.callback),
    # Serve static files directly from STATIC_ROOT
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

# Catch-all for SPA index.html - MUST be the last entry
urlpatterns += [
    re_path(r'^.*$', serve_react_app),
]