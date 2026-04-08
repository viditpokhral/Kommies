from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import SuperUser


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={
            "autofocus": True,
            "placeholder": "you@example.com",
            "autocomplete": "email",
        }),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "placeholder": "Your password",
            "autocomplete": "current-password",
        }),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        try:
            su = SuperUser.objects.get(email=user.email, deleted_at__isnull=True)
        except SuperUser.DoesNotExist:
            raise ValidationError("Account not found.", code="invalid_login")

        if not su.email_verified:
            raise ValidationError(
                "Please verify your email before signing in. Check your inbox or resend the link.",
                code="email_not_verified",
            )