"""
Vues PWA : abonnement aux notifications push.
"""
import json
import logging
import os

from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST

from ..models import PushSubscription

logger = logging.getLogger(__name__)


def service_worker(request):
    """Sert le service worker à la racine afin qu'il puisse couvrir l'application."""
    try:
        worker_file = staticfiles_storage.open("pwa/sw.js")
    except FileNotFoundError as exc:
        raise Http404("Service worker introuvable.") from exc
    response = FileResponse(worker_file, content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_POST
@login_required
def push_subscribe(request):
    """Enregistre l'abonnement push d'un utilisateur."""
    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        auth = data["keys"]["auth"]
        p256dh = data["keys"]["p256dh"]
        if not all(isinstance(value, str) for value in (endpoint, auth, p256dh)):
            raise ValueError
        URLValidator(schemes=["https"])(endpoint)
        if len(endpoint) > 500 or len(auth) > 100 or len(p256dh) > 100:
            raise ValueError
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError):
        return JsonResponse({"ok": False, "error": "Abonnement push invalide."}, status=400)

    try:
        sub, created = PushSubscription.objects.update_or_create(
            utilisateur=request.user,
            endpoint=endpoint,
            defaults={
                "auth": auth,
                "p256dh": p256dh,
            },
        )
        return JsonResponse({"ok": True, "created": created})
    except Exception:
        logger.exception("Impossible d'enregistrer un abonnement push")
        return JsonResponse({"ok": False, "error": "Impossible d'enregistrer l'abonnement."}, status=500)



def envoyer_notification_push(utilisateur, titre, corps, url=None):
    """Envoie une notification push à un utilisateur.
    Nécessite pywebpush : pip install pywebpush
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return False

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY")
    vapid_public = os.environ.get("VAPID_PUBLIC_KEY")
    if not vapid_private or not vapid_public:
        return False

    subs = PushSubscription.objects.filter(utilisateur=utilisateur)
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"auth": sub.auth, "p256dh": sub.p256dh},
                },
                data=json.dumps({"title": titre, "body": corps, "url": url or "/"}),
                vapid_private_key=vapid_private,
                vapid_public_key=vapid_public,
            )
        except WebPushException:
            sub.delete()
    return True
