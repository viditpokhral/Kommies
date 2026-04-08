from django.urls import path
from . import views

app_name = "commenter"

urlpatterns = [
    path("login/",                          views.login_view,           name="login"),
    path("register/",                       views.register_view,        name="register"),
    path("logout/",                         views.logout_view,          name="logout"),
    path("verify-email/<str:token>/",       views.verify_email,         name="verify-email"),
    path("profile/",                        views.profile,              name="profile"),
    path("history/",                        views.history,              name="history"),
    path("settings/",                       views.settings_view,        name="settings"),
    path("forgot-password/",               views.forgot_password,      name="forgot-password"),
    path("reset-password/<str:token>/",    views.reset_password,       name="reset-password"),
]