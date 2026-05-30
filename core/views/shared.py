"""
Fonctions partagées entre les modules de vues UPGCExam.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models import Activite, Sujet, Verification
from ..utils import envoyer_code_verification, generer_code_verification


def salutation():
    heure = timezone.now().hour
    if 6 <= heure < 12:
        return "Bonjour"
    if 12 <= heure < 18:
        return "Bon après-midi"
    if 18 <= heure < 22:
        return "Bonsoir"
    return "Bonne nuit"


def _sujets_accessibles(request):
    """Sujets actifs — les sujets 'restreint' ne sont visibles que par les administrateurs."""
    qs = Sujet.objects.filter(statut="actif").select_related("filiere", "matiere", "niveau")
    if not request.user.is_staff:
        qs = qs.filter(visibilite="visible")
    return qs


def _creer_code_verification(email, request=None):
    Verification.objects.filter(email=email, utilise=False).update(utilise=True)
    code = generer_code_verification()
    Verification.objects.create(
        email=email,
        code=code,
        expire_le=timezone.now() + timedelta(minutes=10),
    )
    try:
        envoyer_code_verification(email, code)
    except Exception:
        if settings.DEBUG:
            msg = "Email non envoyé (configurez SMTP). Consultez la console du serveur."
            if request:
                messages.warning(request, msg)
        else:
            raise
    return code


def _get_sujet_modifiable(request, sujet_id):
    """Retourne le sujet modifiable — les admins peuvent tout modifier,
    les etudiants ne peuvent modifier que leurs propres sujets (actifs ou archivés)."""
    if request.user.is_staff:
        return get_object_or_404(Sujet, id=sujet_id)
    return get_object_or_404(
        Sujet,
        id=sujet_id,
        publie_par=request.user,
    )
