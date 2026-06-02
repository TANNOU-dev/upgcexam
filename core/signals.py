"""Nettoyage des fichiers PDF remplacés ou supprimés."""
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Sujet


def _delete_file_after_commit(field_file):
    if field_file and field_file.name:
        transaction.on_commit(lambda: field_file.storage.delete(field_file.name))


@receiver(pre_save, sender=Sujet)
def remember_replaced_pdf(sender, instance, **kwargs):
    """Mémorise l'ancien PDF avant le remplacement d'un sujet."""
    if not instance.pk:
        return
    try:
        previous = sender.objects.only("fichier_pdf").get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if previous.fichier_pdf.name != instance.fichier_pdf.name:
        instance._replaced_pdf = previous.fichier_pdf


@receiver(post_save, sender=Sujet)
def delete_replaced_pdf(sender, instance, **kwargs):
    """Supprime l'ancien PDF après enregistrement réussi du nouveau."""
    replaced_pdf = getattr(instance, "_replaced_pdf", None)
    _delete_file_after_commit(replaced_pdf)
    if replaced_pdf is not None:
        del instance._replaced_pdf


@receiver(post_delete, sender=Sujet)
def delete_subject_pdf(sender, instance, **kwargs):
    """Supprime le PDF d'un sujet supprimé, y compris via un QuerySet."""
    _delete_file_after_commit(instance.fichier_pdf)
