from django.utils import timezone

from .models import PresenceSession

INACTIVITE_LIMITE_SEC = 15 * 60  # 15 minutes d'inactivité = nouvelle session


def enregistrer_presence(get_response):
    """Middleware : enregistre automatiquement le temps passé par l'utilisateur connecté.
    
    Fonctionnement :
    - Chaque requête crée/met à jour une session de présence.
    - Si la dernière requête date de plus de 15 min, on crée une nouvelle session.
    - Le temps est calculé à partir du début de la session jusqu'à la dernière requête.
    """

    def middleware(request):
        if request.user.is_authenticated:
            try:
                now = timezone.now()
                derniere = (
                    PresenceSession.objects.filter(utilisateur=request.user)
                    .order_by("-debut")
                    .first()
                )

                if derniere is None:
                    # Première session de l'utilisateur
                    PresenceSession.objects.create(
                        utilisateur=request.user,
                        debut=now,
                        fin=now,
                        secondes=0,
                    )
                else:
                    ecart = (now - (derniere.fin or derniere.debut)).total_seconds()

                    if ecart <= INACTIVITE_LIMITE_SEC:
                        # Session active → temps total depuis le début de la session
                        derniere.secondes = int(max(0, (now - derniere.debut).total_seconds()))
                        derniere.fin = now
                        derniere.save(update_fields=["fin", "secondes"])
                    else:
                        # Inactivité > 15 min → finaliser l'ancienne session
                        derniere.secondes = int(max(0, (now - derniere.debut).total_seconds()))
                        derniere.fin = now
                        derniere.save(update_fields=["fin", "secondes"])
                        PresenceSession.objects.create(
                            utilisateur=request.user,
                            debut=now,
                            fin=now,
                            secondes=0,
                        )
            except Exception:
                pass  # Ne pas casser le site si le middleware plante

        return get_response(request)

    return middleware
