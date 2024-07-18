from .base import *


# DEBUG =  bool(int(os.environ.get("DEBUG", default=1)))
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

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: True,
}

LANGUAGE_CODE = 'en'
 