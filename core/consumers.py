"""
WebSocket consumer — tracking temps réel de la présence.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import PresenceSession


class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        if not self.user.is_authenticated:
            return

        try:
            data = json.loads(text_data)
            secondes = int(data.get("seconds", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            return

        if secondes < 0:
            return

        await self.enregistrer_presence(secondes)

    async def disconnect(self, code):
        pass

    @database_sync_to_async
    def enregistrer_presence(self, secondes):
        maintenant = timezone.now()
        derniere = (
            PresenceSession.objects.filter(utilisateur=self.user)
            .order_by("-debut")
            .first()
        )

        if derniere and (maintenant - derniere.debut).total_seconds() < 15 * 60:
            # Toujours mettre à jour : le compteur client (sessionStorage)
            # ne se réinitialise pas entre les pages du même onglet.
            # Si un nouvel onglet envoie une valeur plus petite, on la prend
            # quand même — elle finira par dépasser l'ancienne après qques min.
            derniere.secondes = secondes
            derniere.fin = maintenant
            derniere.save(update_fields=["secondes", "fin"])
        else:
            PresenceSession.objects.create(
                utilisateur=self.user,
                debut=maintenant,
                fin=maintenant,
                secondes=secondes,
            )
