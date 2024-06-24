from .base import *


DEBUG = True

INSTALLED_APPS += ["debug_toolbar",]
MIDDLEWARE += [ "debug_toolbar.middleware.DebugToolbarMiddleware",]

ROOT_URLCONF = 'core.urls.urls_dev'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

