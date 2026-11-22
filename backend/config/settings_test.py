"""Test settings: production settings plus the few things tests need. DEBUG stays off."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-signing-key-that-is-long-enough")
os.environ.setdefault("AUTH_THROTTLE_RATE", "10/min")

from config.settings import *  # noqa: E402,F403

# Hashing passwords properly is slow on purpose; tests create many users, so use a fast hasher here only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
