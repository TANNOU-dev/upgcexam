from django.utils import timezone

from .models import PresenceSession

INACTIVITE_LIMITE_SEC = 30 * 60  # 30 minutes → nouvelle session si dépassé


def enregistrer_presence(get_response):
    """Middleware : enregistre automatiquement le temps passé par l'utilisateur connecté."""

    def middleware(request):
        if request.user.is_authenticated:
            now = timezone.now()
            # Récupère la dernière session (ouverte ou fermée)
            derniere_session = (
                PresenceSession.objects.filter(utilisateur=request.user)
                .order_by("-debut")
                .first()
            )

            if derniere_session:
                ecart = (now - derniere_session.debut).total_seconds()
                if ecart <= INACTIVITE_LIMITE_SEC:
                    # Session encore active → on cumule le temps
                    temps_depuis_derniere_requete = max(
                        0, (now - (derniere_session.fin or derniere_session.debut)).total_seconds()
                    )
                    derniere_session.secondes += int(temps_depuis_derniere_requete)
                    derniere_session.fin = now
                    derniere_session.save(update_fields=["fin", "secondes"])
                else:
                    # Trop long → on ferme et on crée une nouvelle
                    derniere_session.fin = now
                    derniere_session.save(update_fields=["fin"])
                    PresenceSession.objects.create(
                        utilisateur=request.user,
                        debut=now,
                        fin=now,
                        secondes=0,
                    )
            else:
                # Première session de l'utilisateur
                PresenceSession.objects.create(
                    utilisateur=request.user,
                    debut=now,
                    fin=now,
                    secondes=0,
                )

        return get_response(request)

    return middleware
