"""
ASGI config — WebSocket + HTTP.
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path)
except ImportError:
    pass

from django.core.asgi import get_asgi_application

# L'application HTTP Django standard
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from core.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
