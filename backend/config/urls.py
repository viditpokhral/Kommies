"""
URL Configuration for Comment Platform Backend
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from apps.dashboard import views as dashboard_views
from apps.dashboard.forms import EmailLoginForm

urlpatterns = [
    # Redirect root to dashboard
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),

    # Django admin
    path('admin/', admin.site.urls),

    # Apps
    path('dashboard/', include('apps.dashboard.urls')),
    path('analytics/',  include('apps.analytics.urls')),
    path('moderation/', include('apps.moderation.urls')),

    # Internal API
    path('api/', include('apps.dashboard.api_urls')),

    # Auth
    path('accounts/login/',    auth_views.LoginView.as_view(authentication_form=EmailLoginForm),   name='login'),
    path('accounts/logout/',   auth_views.LogoutView.as_view(),  name='logout'),
    path('accounts/register/', dashboard_views.register,         name='register'),
    path('accounts/verify-email/<str:token>/', dashboard_views.verify_tenant_email, name='verify_email'),  

    path('accounts/password-change/',
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change_form.html',
             success_url='/accounts/password-change/done/',
         ),
         name='password_change'),
    path('accounts/password-change/done/',
         auth_views.PasswordChangeDoneView.as_view(),
         name='password_change_done'),

    path('accounts/password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             success_url='/accounts/password-reset/done/',
         ),
         name='password_reset'),
    path('accounts/password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html',
         ),
         name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/accounts/reset/done/',
         ),
         name='password_reset_confirm'),
    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html',
         ),
         name='password_reset_complete'),
    path('accounts/verify-email/<str:token>/', dashboard_views.verify_tenant_email,     name='verify_email'),
    path('accounts/resend-verification/',      dashboard_views.resend_verification_email, name='resend_verification'),

    path('commenter/', include('apps.commenter_portal.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin
admin.site.site_header = "Kommies Admin"
admin.site.site_title  = "Kommies"
admin.site.index_title = "Dashboard"