"""Production settings — security hardening from .security, S3 storage, structured logging."""

from .base import *  # noqa: F401,F403
from .base import env
from .security import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")


# Storage — S3 via django-storages
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
            "region_name": env("AWS_S3_REGION_NAME", default="us-east-1"),
            "location": env("AWS_MEDIA_LOCATION", default="media"),
            "file_overwrite": False,
            "default_acl": None,
            "querystring_auth": True,
        },
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
            "region_name": env("AWS_S3_REGION_NAME", default="us-east-1"),
            "location": env("AWS_STATIC_LOCATION", default="static"),
            "default_acl": "public-read",
            "querystring_auth": False,
        },
    },
}

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.security": {"level": "WARNING", "propagate": True},
        "apps": {"level": "INFO", "propagate": True},
        "integrations": {"level": "INFO", "propagate": True},
    },
}
