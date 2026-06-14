from .settings import *  # noqa
from .settings import BASE_DIR, Q_CLUSTER as BASE_Q_CLUSTER, STORAGES

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "tmp" / "test.sqlite3",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
MEDIA_ROOT = BASE_DIR / "tmp" / "test-media"
STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
Q_CLUSTER = {**BASE_Q_CLUSTER, "sync": True, "orm": "default"}
Q_CLUSTER.pop("redis", None)
