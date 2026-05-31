"""
Vues PWA : abonnement aux notifications push.
"""
import json
import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from ..models import PushSubscription


@require_POST
@login_required
def push_subscribe(request):
    """Enregistre l'abonnement push d'un utilisateur."""
    try:
        data = json.loads(request.body)
        sub, created = PushSubscription.objects.update_or_create(
            utilisateur=request.user,
            endpoint=data["endpoint"],
            defaults={
                "auth": data["keys"]["auth"],
                "p256dh": data["keys"]["p256dh"],
            },
        )
        return JsonResponse({"ok": True, "created": created})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


@require_POST
@login_required
def ping_presence(request):
    """Reçoit le temps écoulé côté client et met à jour la session."""
    try:
        data = json.loads(request.body)
        secondes = int(data.get("seconds", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Données invalides"}, status=400)

    if secondes < 0:
        return JsonResponse({"ok": False, "error": "seconds négatif"}, status=400)

    from django.utils import timezone
    from ..models import PresenceSession

    now = timezone.now()
    derniere = (
        PresenceSession.objects.filter(utilisateur=request.user)
        .order_by("-debut")
        .first()
    )

    if derniere and (now - derniere.debut).total_seconds() < 15 * 60:
        # Session active : on garde le max (temps réel côté client vs serveur)
        if secondes > derniere.secondes:
            derniere.secondes = secondes
            derniere.fin = now
            derniere.save(update_fields=["secondes", "fin"])
    else:
        # Nouvelle session
        PresenceSession.objects.create(
            utilisateur=request.user,
            debut=now,
            fin=now,
            secondes=secondes,
        )

    return JsonResponse({"ok": True, "seconds": secondes})


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
