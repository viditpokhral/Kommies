"""
Dashboard URL Configuration
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Home
    path('', views.dashboard_home, name='home'),

    # Website
    path('website/add/',                                         views.add_website,      name='add-website'),
    path('website/<uuid:website_id>/',                           views.website_detail,   name='website-detail'),
    path('website/<uuid:website_id>/moderation/',                views.moderation_queue, name='moderation-queue'),
    path('website/<uuid:website_id>/analytics/',                 views.analytics,        name='analytics'),
    path('website/<uuid:website_id>/api-test/',                  views.api_test,         name='api-test'),
    path('website/<uuid:website_id>/settings/',                  views.website_settings, name='website-settings'),
    path('website/<uuid:website_id>/rotate-keys/',               views.rotate_keys,      name='rotate-keys'),
    path('website/<uuid:website_id>/delete/',                    views.delete_website,   name='delete-website'),

    # Moderation action
    path('website/<uuid:website_id>/comment/<uuid:comment_id>/moderate/', views.moderate_comment, name='moderate-comment'),

    # Bans
    path('website/<uuid:website_id>/bans/',                      views.ban_list,         name='ban-list'),
    path('website/<uuid:website_id>/bans/<uuid:ban_id>/remove/', views.ban_remove,       name='ban-remove'),

    # Members
    path('website/<uuid:website_id>/members/',                   views.members_list,     name='members-list'),

    # Admin panel
    path('admin-panel/',                                         views.admin_dashboard,      name='admin-home'),
    path('admin-panel/tenants/',                                 views.admin_tenants,        name='admin-tenants'),
    path('admin-panel/tenants/<uuid:user_id>/',                  views.admin_tenant_detail,  name='admin-tenant-detail'),
    path('admin-panel/tenants/<uuid:user_id>/status/',           views.admin_tenant_status,  name='admin-tenant-status'),
    path('admin-panel/comments/',                                views.admin_comments,       name='admin-comments'),
]