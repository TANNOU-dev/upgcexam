"""Utilitaires partagés (validation fichiers, emails, etc.)."""
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail

MAX_PDF_SIZE = 10 * 1024 * 1024


def generer_code_verification():
    return f"{secrets.randbelow(1_000_000):06d}"


def est_fichier_pdf(uploaded_file):
    """Vérifie la signature magique %PDF-, pas seulement le content-type client."""
    if not uploaded_file:
        return False
    pos = uploaded_file.tell()
    uploaded_file.seek(0)
    header = uploaded_file.read(5)
    uploaded_file.seek(pos)
    return header.startswith(b"%PDF-")


def valider_pdf_upload(uploaded_file):
    """Valide la taille et la signature d'un PDF, y compris dans Django Admin."""
    if not uploaded_file:
        raise ValidationError("Un fichier PDF est requis.")
    if uploaded_file.size > MAX_PDF_SIZE:
        raise ValidationError("Le fichier PDF ne doit pas dépasser 10 Mo.")
    if not est_fichier_pdf(uploaded_file):
        raise ValidationError("Seuls les fichiers PDF valides sont acceptés.")


def formater_taille_pdf(size_bytes):
    if size_bytes is None:
        return None
    if size_bytes < 1024:
        return f"{size_bytes} o"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} Ko"
    return f"{size_bytes / (1024 * 1024):.1f} Mo"


def envoyer_code_verification(email, code):
    """Envoie le code par email ; en dev sans SMTP, le message reste dans la console."""
    sujet = "UPGCExam — Code de vérification"
    message = (
        f"Votre code de vérification UPGCExam est : {code}\n\n"
        "Ce code expire dans 10 minutes.\n"
        "Si vous n'avez pas demandé ce code, ignorez ce message."
    )
    send_mail(
        sujet,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
