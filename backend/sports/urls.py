from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('nfl.urls')),  # Include your app's URLs at the root
]
