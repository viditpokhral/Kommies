"""
Django settings for Comment Platform backend
Backend handles: Admin UI, Analytics Dashboards, User Management
"""

import os
import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured  # type: ignore

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# ── SECURITY SETTINGS (PRODUCTION-SAFE) ──────────────────────────────────────

# Parse DEBUG from environment
DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

# SECRET_KEY validation - MUST be set in production
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "SECRET_KEY environment variable must be set when DEBUG=False. "
            "Generate one with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )
    else:
        # Only allow default in DEBUG mode
        SECRET_KEY = 'django-insecure-dev-key-ONLY-FOR-DEVELOPMENT'
        print("WARNING: Using default SECRET_KEY in DEBUG mode. Never use this in production!")

# ALLOWED_HOSTS validation
ALLOWED_HOSTS = [
    host.strip() 
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') 
    if host.strip()
]
if not ALLOWED_HOSTS and not DEBUG:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS cannot be empty when DEBUG=False. "
        "Set the ALLOWED_HOSTS environment variable with comma-separated hostnames."
    )

# Application definition
INSTALLED_APPS = [
    # Admin theme (must be before django.contrib.admin)
    'admin_interface',
    'colorfield',
    
    # Django built-in
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'corsheaders',
    'django_extensions',
    
    # Your apps
    'apps.dashboard',
    'apps.analytics',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files
    'corsheaders.middleware.CorsMiddleware',       # CORS
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ── DATABASE (PRODUCTION-SAFE) ────────────────────────────────────────────────

# Validate DB_PASSWORD in production
DB_PASSWORD = os.getenv('DB_PASSWORD')
if not DB_PASSWORD and not DEBUG:
    raise ImproperlyConfigured(
        "DB_PASSWORD environment variable must be set when DEBUG=False. "
        "This is a security requirement to prevent running in production without proper credentials."
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'comment_platform'),
        'USER': os.getenv('DB_USER', 'comment_platform_admin'),
        'PASSWORD': DB_PASSWORD or 'dev-only-password',  # Falls back only in DEBUG mode
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            # Search all schemas used by FastAPI
            'options': '-c search_path=public,auth,core,billing,moderation,analytics'
        }
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Only include STATICFILES_DIRS if the directory exists
if (BASE_DIR / 'static').exists():
    STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ── CORS Configuration ────────────────────────────────────────────────────────
# Allow FastAPI to call Django APIs

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",  # FastAPI local
    "http://127.0.0.1:8000",  # FastAPI local alternative
    "http://api:8000",        # FastAPI in Docker
]

# Add production origins if specified
CORS_EXTRA_ORIGINS = os.getenv('CORS_ORIGINS', '')
if CORS_EXTRA_ORIGINS:
    CORS_ALLOWED_ORIGINS.extend([
        origin.strip() 
        for origin in CORS_EXTRA_ORIGINS.split(',') 
        if origin.strip()
    ])

CORS_ALLOW_CREDENTIALS = True


# ── FastAPI Integration ───────────────────────────────────────────────────────

FASTAPI_URL = os.getenv('FASTAPI_URL', 'http://localhost:8000')
FASTAPI_ADMIN_SECRET = os.getenv('FASTAPI_ADMIN_SECRET', '')  # Shared secret for admin calls


# ── Django REST Framework ─────────────────────────────────────────────────────

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}


# ── Admin Interface Theme ─────────────────────────────────────────────────────

X_FRAME_OPTIONS = 'SAMEORIGIN'
SILENCED_SYSTEM_CHECKS = ['security.W019']  # Allow iframe for admin theme


# ── Security Settings (Production) ────────────────────────────────────────────

if not DEBUG:
    # HTTPS/Security
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Additional security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'


# ── Logging ───────────────────────────────────────────────────────────────────

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'] if DEBUG else ['console', 'file'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}


# ── Startup Validation ────────────────────────────────────────────────────────

if not DEBUG:
    print(f"✓ Running in PRODUCTION mode")
    print(f"✓ ALLOWED_HOSTS: {ALLOWED_HOSTS}")
    print(f"✓ DATABASE: {DATABASES['default']['HOST']}:{DATABASES['default']['PORT']}")
    print(f"✓ SECRET_KEY: {'*' * 20} (configured)")
else:
    print(f"⚠ Running in DEBUG mode - NOT FOR PRODUCTION")
    print(f"  ALLOWED_HOSTS: {ALLOWED_HOSTS}")