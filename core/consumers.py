"""
WebSocket consumer — tracking temps réel de la présence.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import F
from django.utils import timezone
from .models import PresenceSession

MAX_PRESENCE_DELTA_SECONDS = 30


class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        await self.accept()
        self.last_presence_tick = timezone.now()

    async def receive(self, text_data=None, bytes_data=None):
        if not self.user.is_authenticated:
            return

        try:
            json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        maintenant = timezone.now()
        secondes = min(
            int((maintenant - self.last_presence_tick).total_seconds()),
            MAX_PRESENCE_DELTA_SECONDS,
        )
        self.last_presence_tick = maintenant
        if secondes <= 0:
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
            PresenceSession.objects.filter(pk=derniere.pk).update(
                secondes=F("secondes") + secondes,
                fin=maintenant,
            )
        else:
            PresenceSession.objects.create(
                utilisateur=self.user,
                debut=maintenant,
                fin=maintenant,
                secondes=secondes,
            )
