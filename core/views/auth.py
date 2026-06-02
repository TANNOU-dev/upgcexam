"""
Vues d'authentification : connexion, inscription, vérification email,
mot de passe oublié, paramètres compte.
"""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from ..models import Filiere, Utilisateur, Verification

from ..navigation import safe_next_url
from .shared import creer_code_verification, verifier_code_verification


@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def connexion(request):
    if request.user.is_authenticated:
        return redirect("tableau_de_bord")

    if request.method == "POST":
        username_input = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username_input, password=password)
        if user:
            login(request, user)
            raw_next = request.POST.get("next") or request.GET.get("next") or ""
            return redirect(safe_next_url(raw_next))
        messages.error(request, "Nom d'utilisateur ou mot de passe incorrect")

    next_url = request.GET.get("next", "")
    return render(
        request,
        "core/login.html",
        {
            "next": next_url,
            "inscription_url": (
                f"{reverse('inscription')}?{urlencode({'next': next_url})}"
                if next_url
                else reverse("inscription")
            ),
        },
    )


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def inscription(request):
    if request.user.is_authenticated:
        return redirect("tableau_de_bord")

    filieres = Filiere.objects.all()
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        filiere_id = request.POST.get("filiere", "")

        if not all([username, email, password, password2]):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
        elif password != password2:
            messages.error(request, "Les mots de passe ne correspondent pas")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà utilisé")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur est déjà pris")
        else:
            try:
                validate_password(password, user=User(username=username, email=email))
            except ValidationError as erreurs:
                messages.error(request, " ".join(erreurs.messages))
                return render(request, "core/inscription.html", {"filieres": filieres})
            user = User.objects.create_user(username=username, email=email, password=password)
            profil = Utilisateur.objects.create(user=user)
            if filiere_id:
                try:
                    profil.filiere = Filiere.objects.get(id=filiere_id)
                    profil.save()
                except Filiere.DoesNotExist:
                    pass
            try:
                creer_code_verification(email, request)
            except Exception:
                messages.error(
                    request,
                    "Compte créé mais l'envoi du code a échoué. Contactez l'administration.",
                )
                return redirect("connexion")
            request.session["email_a_verifier"] = email
            messages.info(
                request,
                "Un code de vérification a été envoyé à votre adresse email.",
            )
            return redirect("verification")

    return render(request, "core/inscription.html", {"filieres": filieres})


def verification(request):
    email = request.session.get("email_a_verifier", "")
    next_url = request.GET.get("next") or request.session.get("verification_next", "")
    if next_url:
        request.session["verification_next"] = next_url

    if request.user.is_authenticated and hasattr(request.user, "profil"):
        if request.user.is_staff or request.user.profil.email_verifie:
            request.session.pop("verification_next", None)
            return redirect(safe_next_url(next_url))

    if request.method == "POST":
        code_saisi = request.POST.get("code", "").strip()
        statut = verifier_code_verification(email, code_saisi, Verification.USAGE_EMAIL)
        if statut == "valide":
            request.session.pop("email_a_verifier", None)
            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                user.backend = "django.contrib.auth.backends.ModelBackend"
                login(request, user)
                profil, _ = Utilisateur.objects.get_or_create(user=user)
                profil.email_verifie = True
                profil.save(update_fields=["email_verifie"])
            messages.success(request, "Email vérifié avec succès.")
            request.session.pop("verification_next", None)
            return redirect(safe_next_url(next_url))
        if statut == "bloque":
            messages.error(request, "Trop de tentatives. Le code a été invalidé. Demandez-en un nouveau.")
        elif statut == "expire":
            messages.error(request, "Le code a expiré.")
        else:
            messages.error(request, "Code invalide.")

    return render(
        request,
        "core/verification.html",
        {"email": email, "afficher_code_dev": settings.DEBUG},
    )


@require_POST
@login_required
def deconnexion(request):
    logout(request)
    return redirect("accueil")


@login_required
def parametres(request):
    if request.method == "POST":
        user = request.user
        nouveau_username = request.POST.get("username", "").strip()
        nouvel_email = request.POST.get("email", "").strip().lower()
        ancien_mdp = request.POST.get("ancien_mot_de_passe", "")
        nouveau_mdp = request.POST.get("nouveau_mot_de_passe", "")

        changer_mdp = bool(nouveau_mdp)
        changer_email = bool(nouvel_email and nouvel_email != user.email)
        changer_profil = bool(
            (nouveau_username and nouveau_username != user.username)
            or changer_email
        )

        if not changer_mdp and not changer_profil:
            messages.warning(request, "Aucune modification détectée.")
            return redirect("parametres")

        if changer_email and (not ancien_mdp or not user.check_password(ancien_mdp)):
            messages.error(request, "Mot de passe actuel requis pour modifier votre email.")
            return redirect("parametres")

        if changer_mdp:
            if not ancien_mdp or not user.check_password(ancien_mdp):
                messages.error(request, "Ancien mot de passe incorrect")
                return redirect("parametres")
            try:
                validate_password(nouveau_mdp, user=user)
            except ValidationError as erreurs:
                messages.error(request, " ".join(erreurs.messages))
                return redirect("parametres")

        if nouveau_username and nouveau_username != user.username:
            if User.objects.filter(username=nouveau_username).exclude(id=user.id).exists():
                messages.error(request, "Ce nom d'utilisateur est déjà pris")
                return redirect("parametres")
            user.username = nouveau_username

        if changer_email:
            if User.objects.filter(email=nouvel_email).exclude(id=user.id).exists():
                messages.error(request, "Cet email est déjà utilisé")
                return redirect("parametres")
            user.email = nouvel_email

        if nouveau_mdp:
            user.set_password(nouveau_mdp)
            update_session_auth_hash(request, user)

        user.save()
        if changer_email:
            profil, _ = Utilisateur.objects.get_or_create(user=user)
            profil.email_verifie = False
            profil.save(update_fields=["email_verifie"])
            try:
                creer_code_verification(nouvel_email, request)
            except Exception:
                messages.error(request, "Email mis à jour, mais le code de vérification n'a pas pu être envoyé.")
                return redirect("parametres")
            request.session["email_a_verifier"] = nouvel_email
            messages.info(request, "Un code de vérification a été envoyé à votre nouvelle adresse email.")
            return redirect("verification")

        messages.success(request, "Informations mises à jour avec succès !")
        return redirect("parametres")

    return render(request, "core/parametres.html")


# ─── Mot de passe oublié (flux avec code de vérification) ───────────────

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def password_reset_envoyer(request):
    """Étape 1 : saisir l'email, génère un code de vérification."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        request.session.pop("reset_code_verified", None)
        request.session.pop("reset_code_verified_at", None)
        request.session["reset_email"] = email
        if User.objects.filter(email__iexact=email).exists():
            creer_code_verification(email, request, usage=Verification.USAGE_PASSWORD_RESET)
        messages.success(
            request,
            "Si un compte correspond à cette adresse, un code de vérification a été envoyé.",
        )
        return redirect("password_reset_code")

    return render(request, "core/password_reset.html")


def password_reset_code(request):
    """Étape 2 : saisir le code de vérification."""
    email = request.session.get("reset_email", "")
    if not email:
        return redirect("password_reset")

    if request.method == "POST":
        code_saisi = request.POST.get("code", "").strip()
        statut = verifier_code_verification(email, code_saisi, Verification.USAGE_PASSWORD_RESET)
        if statut == "valide":
            request.session["reset_code_verified"] = True
            request.session["reset_code_verified_at"] = timezone.now().timestamp()
            return redirect("password_reset_new")
        if statut == "bloque":
            messages.error(request, "Trop de tentatives. Le code a été invalidé.")
        elif statut == "expire":
            messages.error(request, "Le code a expiré.")
        else:
            messages.error(request, "Code invalide.")

    return render(request, "core/password_reset_code.html", {"email": email})


def password_reset_new(request):
    """Étape 3 : choisir un nouveau mot de passe."""
    email = request.session.get("reset_email", "")
    code_verified = request.session.get("reset_code_verified", False)
    code_verified_at = request.session.get("reset_code_verified_at")
    if (
        not email
        or not code_verified
        or not code_verified_at
        or timezone.now().timestamp() - code_verified_at > 10 * 60
    ):
        return redirect("password_reset")

    if request.method == "POST":
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        if len(password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
        elif password != password2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
        else:
            try:
                user = User.objects.get(email=email)
                validate_password(password, user=user)
                user.set_password(password)
                user.save()
                request.session.pop("reset_email", None)
                request.session.pop("reset_code_verified", None)
                request.session.pop("reset_code_verified_at", None)
                messages.success(request, "Mot de passe réinitialisé avec succès. Connectez-vous !")
                return redirect("connexion")
            except ValidationError as erreurs:
                messages.error(request, " ".join(erreurs.messages))
            except User.DoesNotExist:
                messages.error(request, "Erreur : compte introuvable.")

    return render(request, "core/password_reset_new.html", {"email": email})
