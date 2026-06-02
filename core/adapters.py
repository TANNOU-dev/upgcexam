from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from core.models import Utilisateur


class UPGCExamSocialAdapter(DefaultSocialAccountAdapter):
    """Crée automatiquement le profil Utilisateur après une connexion sociale."""

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        email = user.email.lower()
        email_is_verified = any(
            address.verified and address.email.lower() == email
            for address in sociallogin.email_addresses
        )
        Utilisateur.objects.get_or_create(
            user=user,
            defaults={"filiere": None, "email_verifie": email_is_verified},
        )
        return user
