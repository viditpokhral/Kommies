"""
URL Configuration for Comment Platform Backend
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Redirect root to dashboard
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    
    # Admin
    path("admin/", admin.site.urls),
    # path("accounts/", include("django.contrib.auth.urls")),

    
    # Apps
    path('dashboard/', include('apps.dashboard.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('moderation/', include('apps.moderation.urls')),
    
    # API (if needed for internal endpoints)
    path('api/', include('apps.dashboard.api_urls')),

    # # Individual auth URLs
    path('accounts/login/',  auth_views.LoginView.as_view(),  name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password-change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    path('accounts/password-change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('accounts/password-reset/',      auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('accounts/password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('accounts/reset/done/',          auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin
admin.site.site_header = "💬 Comment Platform Admin"
admin.site.site_title = "Comment Platform"
admin.site.index_title = "Dashboard"
