from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from core.models import Utilisateur


class UPGCExamSocialAdapter(DefaultSocialAccountAdapter):
    """Crée automatiquement le profil Utilisateur après une connexion sociale."""

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        # Créer le profil Utilisateur s'il n'existe pas
        Utilisateur.objects.get_or_create(user=user, defaults={"filiere": None})
        return user
