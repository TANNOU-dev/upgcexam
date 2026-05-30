"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

# Charger .env manuellement avant Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path)
except ImportError:
    pass

from django.core.asgi import get_asgi_application

application = get_asgi_application()
