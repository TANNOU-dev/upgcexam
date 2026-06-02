import os


def pwa_settings(request):
    """Expose uniquement la clé VAPID publique nécessaire à l'abonnement push."""
    return {"vapid_public_key": os.environ.get("VAPID_PUBLIC_KEY", "")}
