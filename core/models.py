from django.db import models
from django.contrib.auth.models import User

from .utils import formater_taille_pdf


class Filiere(models.Model):
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Filière"
        verbose_name_plural = "Filières"

    def __str__(self):
        return f"{self.code} - {self.nom}"


class Niveau(models.Model):
    nom = models.CharField(max_length=20)

    class Meta:
        verbose_name = "Niveau"
        verbose_name_plural = "Niveaux"

    def __str__(self):
        return self.nom


class Matiere(models.Model):
    nom = models.CharField(max_length=150)
    filiere = models.ForeignKey(Filiere, on_delete=models.CASCADE, related_name="matieres")

    class Meta:
        verbose_name = "Matière"
        verbose_name_plural = "Matières"

    def __str__(self):
        return f"{self.nom} ({self.filiere.code})"


class Utilisateur(models.Model):
    ROLE_CHOICES = [("etudiant", "Étudiant"), ("admin", "Administrateur")]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profil")
    filiere = models.ForeignKey(
        Filiere, on_delete=models.SET_NULL, null=True, blank=True, related_name="etudiants"
    )
    niveau = models.ForeignKey(
        Niveau, on_delete=models.SET_NULL, null=True, blank=True, related_name="etudiants"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="etudiant")
    email_verifie = models.BooleanField(default=False)
    avatar = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.user.username


class Sujet(models.Model):
    STATUT_CHOICES = [
        ("actif", "Actif"),
        ("en_attente", "En attente de validation"),
        ("archive", "Archivé"),
    ]
    VISIBILITE_CHOICES = [("visible", "Visible"), ("restreint", "Restreint")]
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    filiere = models.ForeignKey(Filiere, on_delete=models.CASCADE, related_name="sujets")
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="sujets")
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE, related_name="sujets")
    annee_academique = models.CharField(max_length=9)
    fichier_pdf = models.FileField(upload_to="sujets/")
    taille_pdf = models.CharField(max_length=10, blank=True, null=True)
    auteur_nom = models.CharField(max_length=100, blank=True, null=True)
    publie_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sujets_publies"
    )
    statut = models.CharField(max_length=12, choices=STATUT_CHOICES, default="actif")
    visibilite = models.CharField(max_length=10, choices=VISIBILITE_CHOICES, default="visible")
    date_publication = models.DateField(auto_now_add=True)
    vues = models.IntegerField(default=0)
    telechargements = models.IntegerField(default=0)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sujet"
        verbose_name_plural = "Sujets"

    def __str__(self):
        return f"{self.titre} - {self.matiere.nom} ({self.annee_academique})"

    def save(self, *args, **kwargs):
        if self.fichier_pdf:
            try:
                size = self.fichier_pdf.size
            except (OSError, ValueError):
                size = None
            if size is not None:
                self.taille_pdf = formater_taille_pdf(size)
        super().save(*args, **kwargs)


class Telechargement(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="telechargements")
    sujet = models.ForeignKey(Sujet, on_delete=models.CASCADE, related_name="telechargements_sujet")
    telecharge_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Téléchargement"
        verbose_name_plural = "Téléchargements"

    def __str__(self):
        return f"{self.utilisateur.username} → {self.sujet.titre}"


class Activite(models.Model):
    TYPE_CHOICES = [
        ("telechargement", "Téléchargement"),
        ("consultation", "Consultation"),
        ("publication", "Publication"),
        ("profil_modifie", "Profil modifié"),
    ]
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activites")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    sujet = models.ForeignKey(
        Sujet, on_delete=models.SET_NULL, null=True, blank=True, related_name="activites"
    )
    description = models.TextField(blank=True, null=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Activité"
        verbose_name_plural = "Activités"
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.utilisateur.username} - {self.type}"


class PresenceSession(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="presences")
    debut = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)
    secondes = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Session de présence"
        verbose_name_plural = "Sessions de présence"
        ordering = ["-debut"]

    def __str__(self):
        return f"{self.utilisateur.username} - {self.secondes}s"


class PushSubscription(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500)
    auth = models.CharField(max_length=100)
    p256dh = models.CharField(max_length=100)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abonnement Push"
        verbose_name_plural = "Abonnements Push"

    def __str__(self):
        return f"Push: {self.utilisateur.username}"


class Verification(models.Model):
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
    expire_le = models.DateTimeField(db_index=True)
    utilise = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Vérification"
        verbose_name_plural = "Vérifications"

    def __str__(self):
        return f"{self.email} - {self.code}"
