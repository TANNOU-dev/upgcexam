from django.utils import timezone

from .models import PresenceSession

INACTIVITE_LIMITE_SEC = 30 * 60  # 30 minutes → nouvelle session si dépassé


def enregistrer_presence(get_response):
    """Middleware : enregistre automatiquement le temps passé par l'utilisateur connecté."""

    def middleware(request):
        if request.user.is_authenticated:
            now = timezone.now()
            # Cherche une session encore ouverte (fin = None)
            session_active = (
                PresenceSession.objects.filter(
                    utilisateur=request.user, fin__isnull=True
                )
                .order_by("-debut")
                .first()
            )

            if session_active:
                ecart = (now - session_active.debut).total_seconds()
                if ecart <= INACTIVITE_LIMITE_SEC:
                    # Prolonge la session en cours
                    secondes_ajoutees = max(
                        0, (now - (session_active.fin or session_active.debut)).total_seconds()
                    )
                    # Si `fin` n'a jamais été définie, c'est la 1ere extension
                    if session_active.fin is None:
                        secondes_ajoutees = max(
                            0, (now - session_active.debut).total_seconds()
                        )
                        session_active.secondes = int(secondes_ajoutees)
                    else:
                        session_active.secondes += int(secondes_ajoutees)
                    session_active.fin = now
                    session_active.save(update_fields=["fin", "secondes"])
                else:
                    # Trop long → ferme l'ancienne + crée une nouvelle
                    session_active.fin = session_active.fin or now
                    session_active.save(update_fields=["fin"])
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
