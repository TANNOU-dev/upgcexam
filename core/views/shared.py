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
from django.db.models import Q

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


def creer_code_verification(email, request=None, usage=Verification.USAGE_EMAIL):
    Verification.objects.filter(email=email, utilise=False).update(utilise=True)
    code = generer_code_verification()
    Verification.objects.create(
        email=email,
        code=code,
        expire_le=timezone.now() + timedelta(minutes=10),
        usage=usage,
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



def valider_fichier_pdf(fichier, taille_max=10):
    """Valide un fichier PDF (taille + contenu). Retourne (ok, message)."""
    if fichier.size > taille_max * 1024 * 1024:
        return False, f"Le fichier PDF ne doit pas dépasser {taille_max} Mo."
    from ..utils import est_fichier_pdf
    if not est_fichier_pdf(fichier):
        return False, "Seuls les fichiers PDF valides sont acceptés."
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
