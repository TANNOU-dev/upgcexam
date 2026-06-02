from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse


def email_verifie_required(view_func):
    """Redirige vers la vérification email si le profil n'est pas validé (sauf staff)."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            profil = getattr(request.user, "profil", None)
            if profil is None or not profil.email_verifie:
                destination = reverse("verification")
                chemin = request.get_full_path()
                if chemin and chemin != destination:
                    destination = f"{destination}?{urlencode({'next': chemin})}"
                return redirect(destination)
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_required(view_func):
    """Remplace le guard 'if not request.user.is_staff' répété dans chaque vue admin."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Accès réservé aux administrateurs.")
            return redirect("tableau_de_bord")
        return view_func(request, *args, **kwargs)

    return wrapper
