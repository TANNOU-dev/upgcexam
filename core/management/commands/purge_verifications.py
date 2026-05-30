"""
Commande : python manage.py purge_verifications

Supprime les codes de vérification expirés ou déjà utilisés.
Planification recommandée : cron hebdomadaire.
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Verification

logger = logging.getLogger("core")


class Command(BaseCommand):
    help = "Supprime les codes de vérification expirés ou déjà utilisés."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche le nombre sans supprimer.",
        )

    def handle(self, *args, **options):
        qs = Verification.objects.filter(
            expire_le__lt=timezone.now()
        ) | Verification.objects.filter(utilise=True)

        count = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"[dry-run] {count} code(s) seraient supprimés.")
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} code(s) supprimés."))
        logger.info(f"Purge: {deleted} codes supprimés.")
