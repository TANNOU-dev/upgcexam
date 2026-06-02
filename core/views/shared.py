"""
Fonctions partagées entre les modules de vues UPGCExam.
"""
from datetime import timedelta
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models import Sujet, Verification
from ..utils import envoyer_code_verification, generer_code_verification, valider_pdf_upload


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


def creer_code_verification(email, request=None, usage=Verification.USAGE_EMAIL):
    """Crée un OTP unique pour un email et un usage donnés."""
    Verification.objects.filter(email=email, usage=usage, utilise=False).update(utilise=True)
    code = generer_code_verification()
    Verification.objects.create(
        email=email,
        code=code,
        usage=usage,
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

def verifier_code_verification(email, code_saisi, usage):
    """Valide un OTP et compte aussi les tentatives portant sur un mauvais code."""
    verification = (
        Verification.objects.filter(email=email, usage=usage, utilise=False)
        .order_by("-expire_le")
        .first()
    )
    if verification is None:
        return "invalide"
    if not verification.est_valide():
        return "bloque" if verification.tentatives >= verification.MAX_TENTATIVES else "expire"
    if not secrets.compare_digest(verification.code, code_saisi):
        return "bloque" if verification.enregistrer_echec() else "invalide"

    verification.utilise = True
    verification.save(update_fields=["utilise"])
    return "valide"


def _annees_actives(sujets_qs=None):
    """Années académiques distinctes pour formulaires d'ajout/modif."""
    if sujets_qs is None:
        qs = Sujet.objects.filter(statut="actif")
    else:
        qs = sujets_qs
    return list(
        qs.values_list("annee_academique", flat=True)
        .distinct()
        .order_by("-annee_academique")
    )



def valider_fichier_pdf(fichier):
    """Valide un fichier PDF (taille + contenu). Retourne (ok, message)."""
    try:
        valider_pdf_upload(fichier)
    except ValidationError as exc:
        return False, exc.messages[0]
    return True, ""


def notifier_admins(titre, message, url=""):
    """Envoie une notification push à tous les administrateurs."""
    admins = User.objects.filter(is_staff=True)
    if not admins.exists():
        return
    from .pwa import envoyer_notification_push
    for admin in admins:
        envoyer_notification_push(
            admin,
            titre,
            message,
            url=url,
        )


def _get_sujet_modifiable(request, sujet_id):
    """Retourne le sujet modifiable — les admins peuvent tout modifier,
    les etudiants peuvent modifier leurs propres sujets (tout statut confondu)."""
    if request.user.is_staff:
        return get_object_or_404(Sujet, id=sujet_id)
    return get_object_or_404(
        Sujet,
        id=sujet_id,
        publie_par=request.user,
    )
