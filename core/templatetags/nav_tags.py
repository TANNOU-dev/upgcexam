from urllib.parse import urlencode

from django import template
from django.urls import reverse

from core.navigation import query_bibliotheque, safe_next_url, url_connexion_avec_next

register = template.Library()


@register.simple_tag
def connexion_pour(chemin):
    return url_connexion_avec_next(chemin)


@register.simple_tag(takes_context=True)
def ajouter_sujet_url(context):
    request = context["request"]
    if request.user.is_authenticated:
        return reverse("ajouter_sujet")
    return url_connexion_avec_next(reverse("ajouter_sujet"))


@register.simple_tag(takes_context=True)
def detail_sujet_url(context, sujet_id):
    """Fiche sujet si connecté, sinon connexion avec retour vers la fiche."""
    request = context["request"]
    url = reverse("detail_sujet", args=[sujet_id])
    if request.user.is_authenticated:
        return url
    return url_connexion_avec_next(url)


@register.simple_tag(takes_context=True)
def biblio_filtres_suffix(context, prefix="&"):
    """Suffixe pour pagination : &q=... ou vide."""
    request = context["request"]
    qs = query_bibliotheque(request)
    if not qs:
        return ""
    return prefix + qs.lstrip("?")


@register.filter
def safe_next(value, default="/"):
    return safe_next_url(value, default)
