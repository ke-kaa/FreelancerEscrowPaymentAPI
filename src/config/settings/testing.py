"""Test settings — eager Celery, fast hashers, locmem cache/email."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": env.db(
        "TEST_DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/escrow_test",
    ),
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"anon": None, "user": None, "email": None}

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = []
CSRF_TRUSTED_ORIGINS = []
