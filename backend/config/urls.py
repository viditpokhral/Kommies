"""
URL Configuration for Comment Platform Backend
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # Redirect root to dashboard
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Apps
    path('dashboard/', include('apps.dashboard.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('moderation/', include('apps.moderation.urls')),
    
    # API (if needed for internal endpoints)
    path('api/', include('apps.dashboard.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin
admin.site.site_header = "💬 Comment Platform Admin"
admin.site.site_title = "Comment Platform"
admin.site.index_title = "Dashboard"
