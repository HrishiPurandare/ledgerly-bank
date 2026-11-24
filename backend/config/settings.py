"""Ledgerly Bank API settings. Everything that differs between machines comes from environment variables."""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set DJANGO_SECRET_KEY (or DJANGO_DEBUG=true for local development).")
    SECRET_KEY = "dev-only-insecure-key-never-use-in-production"  # noqa: S105 - only with DEBUG on
# The key also signs JWTs (HS256), which needs at least 32 bytes (RFC 7518, section 3.2).
if not DEBUG and len(SECRET_KEY) < 32:
    raise RuntimeError("DJANGO_SECRET_KEY must be at least 32 characters.")
ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
# The admin login posts a form: behind a proxy on another port, Django must trust that origin.
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
SECURE_REFERRER_POLICY = "same-origin"
# Only behind real HTTPS (the local Docker stack is plain HTTP on localhost, so these stay off there).
if os.getenv("LEDGERLY_HTTPS", "false").lower() == "true":
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # the proxy terminates TLS
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "users",
    "core",
    "banking",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves /static/ itself in containers (DEBUG off)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

# SQLite by default (zero setup); Postgres in Docker and CI via DATABASE_URL.
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"  # empty counts as unset
DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=60)}

AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dubai"
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Compressed, but no manifest: a manifest would make tests depend on running collectstatic first.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    # Secure by default: every endpoint needs a logged-in user unless it explicitly opts out.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {"auth": os.getenv("AUTH_THROTTLE_RATE", "10/min")},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    # Without this, rotation is cosmetic: the old refresh token would keep working.
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Ledgerly Bank API",
    "DESCRIPTION": "Fictional banking API used as the system under test for a test-automation portfolio.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # The API description is public (like any documented API); the data behind it is not.
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "COMPONENT_SPLIT_REQUEST": True,
}

# Ledgerly Bank's published limits (data/policies in the Ask Ledgerly chatbot say the same).
LEDGERLY = {
    "DAILY_LIMIT": os.getenv("LEDGERLY_DAILY_LIMIT", "50000.00"),
    "NEW_BENEFICIARY_LIMIT": "10000.00",
    "NEW_BENEFICIARY_HOURS": 24,
    "MAX_BENEFICIARIES": 100,
    "OTP_MINUTES": 5,
    "OTP_MAX_ATTEMPTS": 3,
}

# With DEBUG off, Django's default logging only EMAILS server errors to ADMINS (none here) and prints
# nothing, so a 500 in Docker left no trace at all. Log to the console, where `docker compose logs` reads.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "WARNING")},
}

# OTP emails: printed to the console in development; MailHog in Docker; an in-memory outbox in tests.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "1025"))
DEFAULT_FROM_EMAIL = "Ledgerly Bank <no-reply@ledgerly.example>"
