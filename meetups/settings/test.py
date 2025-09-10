from . import *

DEBUG = True  # Enable debug mode for tests

DATABASES = {
  "default": {
    "ENGINE": "django.db.backends.sqlite3",  # Use SQLite for fast, in-memory tests
    "NAME": ":memory:",  # In-memory database
  }
}

class DisableMigrations:
  def __contains__(self, item):
    return True
  def __getitem__(self, item):
    return None

MIGRATION_MODULES = DisableMigrations()  # Disable migrations during tests

CACHES = {
  "default": {
    "BACKEND": "django.core.cache.backends.dummy.DummyCache",  # Use dummy cache backend for tests
  }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # Use fast password hasher for tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"  # Use in-memory email backend for tests