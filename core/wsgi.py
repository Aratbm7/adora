"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application


DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'core.settings.{DJANGO_ENV}')

application = get_wsgi_application()
