"""
Dashboard URL Configuration
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('website/<uuid:website_id>/', views.website_detail, name='website-detail'),
    path('website/<uuid:website_id>/moderation/', views.moderation_queue, name='moderation-queue'),
    path('website/<uuid:website_id>/analytics/', views.analytics, name='analytics'),
    path('comment/<uuid:comment_id>/moderate/', views.moderate_comment, name='moderate-comment'),
    path('website/<uuid:website_id>/api-test/', views.api_test, name='api-test'),
]
