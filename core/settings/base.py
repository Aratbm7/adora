import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-xz$p@moc34)7x+$7a-u75f=m)hq0j--q#)ubfdaq_od0gzl7z1"

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG =  bool(os.environ.get("DEBUG", default=0))

# ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(" ")
ALLOWED_HOSTS = ["*"]

# Application definition

INSTALLED_APPS = [
    # 'django_daisy',
    "admin_interface",
    "colorfield",
    # 'django_daisy',
    "admin_auto_filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jalali_date",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_yasg",
    "django_filters",
    # "account.apps.AccountConfig",
    "account",
    "adora",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
AUTH_USER_MODEL = "account.User"

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.environ.get("SQL_DATABASE", "adora_db_lo"),
        "USER": os.environ.get("SQL_USER", "adora_user_lo"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "1234_lo"),
        "HOST": os.environ.get("SQL_HOST", "db"),
        "PORT": os.environ.get("SQL_PORT", "6379"),
    }
}

# print("DATABASES",  os.environ.get("SQL_ENGINE" , "Noooooooooooooooooooooooooooooooooooo"))
# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

# LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

LANGUAGES = (
    ("fa", "فارسی"),
    # ('tr', ('Turkce')),
    # ("en", ("English")),
    # ("it", ("Italiano")),
    # ("fr", ("Français")),
    # more than one language is expected here
)
LANGUAGE_CODE = "fa"
TIME_ZONE = "Iran"
PHONENUMBER_DEFAULT_REGION = "IR"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # "rest_framework.authentication.BasicAuthentication",
    ),
}
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://:1234@redis_master:6379/1",  # Auth password is included
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
    "replica": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://:1234@redis_replica:6380/1",  # Reading from replica
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
    "admin_interface": {  # کش مخصوص admin_interface
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://:1234@redis_master:6379/2",  # جدا کردن فضای کش برای admin_interface
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": None,  # کش ادمین همیشه معتبر باشد
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static" # برای collectstatic

STATICFILES_DIRS = [
    BASE_DIR / "staticfiles",  # اطمینان از لود شدن فایل‌های custom
]
# CELERY_BROKER_URL = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/0"
CELERY_BROKER_URL = "redis://:1234@redis_master:6379/0"
CELERY_RESULT_BACKEND = "redis://:1234@redis_master:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Celery beat config
CELERY_BEAT_SCHEDULE = {
    "send_otp_to_phone_number": {
        "task": "account.tasks.send_otp_to_phone",
        # 'schedule': crontab(minute="*/15")
        "schedule": 2,
        "args": ["0909090909", "1111111"],
        # 'kwargs': {}
    }
}


APPEND_SLASH = True
CACHE_TTL = 1 * 60

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"  # Points to the master Redis

CORS_ALLOW_ALL_ORIGINS = True  # Allow all origins (use with caution)
X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]


SESSION_ENGINE = "django.contrib.sessions.backends.cache"  # استفاده از کش برای سشن‌ها
SESSION_CACHE_ALIAS = "default"  # مشخص کردن کش پیش‌فرض برای ذخیره سشن‌ها
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # سشن برای 30 روز معتبر بماند
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # بستن مرورگر باعث خروج از سیستم نشود
SESSION_COOKIE_SECURE = False  # اگر SSL ندارید، باید False باشد
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True  # هر درخواس

# SWAGGER_SETTINGS = {
#     "SECURITY_DEFINITIONS": {"basic": {"type": "basic"}},
#     "USE_SESSION_AUTH": True,
# }
# LOGIN_URL = "rest_framework:login"
# LOGOUT_URL = "rest_framework:logout"
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://adorayadak.ir",
    "https://api.adorayadak.ir",
]


ALLOWED_SMS_CAMPAIGN_PARAM_PATHS = [
    ("profile.get_first_name", "نام"),
    ("profile.get_last_name", "نام خانوادگی"),
    ("profile.get_full_name", "نام کامل"),
    ("user.phone_number_with_zero", "شماره موبایل"),
    ("profile.wallet_balance", "اعتبار کیف پول"),
    ("campaign.start_datetime", "تاریخ شروع کمپین"),
    ("campaign.end_datetime", "تاریخ پایان کمپین"),
    ("campaign.name", "نام کمپین"),
]
