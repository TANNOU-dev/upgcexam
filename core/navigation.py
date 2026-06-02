"""Parcours et redirections entre pages (next, retour, filtres bibliothèque)."""
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(next_url, default=None):
    if default is None:
        default = reverse("tableau_de_bord")
    if (
        next_url
        and next_url.startswith("/")
        and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None)
    ):
        return next_url
    return default


def filtres_bibliotheque(request):
    """Paramètres GET actifs sur la bibliothèque (hors pagination)."""
    params = {}
    for key in ("q", "filiere", "matiere", "annee"):
        val = request.GET.get(key, "").strip()
        if val:
            params[key] = val
    return params


def query_bibliotheque(request):
    params = filtres_bibliotheque(request)
    return f"?{urlencode(params)}" if params else ""


def url_connexion_avec_next(chemin):
    return f"{reverse('connexion')}?{urlencode({'next': chemin})}"


def ctx_retour(request):
    """URL et champ caché pour revenir à la page d'origine après une action."""
    next_url = (request.GET.get("next") or "").strip()
    defaut = reverse("bibliotheque") + query_bibliotheque(request)
    retour_url = safe_next_url(next_url, defaut) if next_url else defaut
    return {
        "retour_url": retour_url,
        "next_hidden": request.get_full_path(),
    }


def redirect_apres_sujet(request, sujet=None, defaut="bibliotheque"):
    """Redirection après création / modification / suppression d'un sujet."""
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url:
        if defaut in ("detail", "detail_sujet") and sujet is not None:
            fallback = reverse("detail_sujet", args=[sujet.id])
        else:
            fallback = reverse(defaut)
        return redirect(safe_next_url(next_url, fallback))

    if sujet is not None and defaut in ("detail", "detail_sujet"):
        return redirect(reverse("detail_sujet", args=[sujet.id]))

    return redirect(reverse("bibliotheque") + query_bibliotheque(request))
