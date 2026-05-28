"""
Configuration de l'interface d'administration Django pour UPGCExam.
"""
from django.contrib import admin
from .models import (
    Filiere,
    Niveau,
    Matiere,
    Utilisateur,
    Sujet,
    Telechargement,
    Activite,
    Verification,
    PresenceSession,
    PushSubscription,
)


# ─── Filière ────────────────────────────────────────────────

@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    list_display = ("ordre", "code", "nom")
    list_display_links = ("code",)
    list_editable = ("ordre",)
    search_fields = ("nom", "code")
    ordering = ("ordre",)

    @admin.action(description="⬆ Déplacer vers le haut")
    def deplacer_vers_le_haut(self, request, queryset):
        for obj in queryset:
            obj.ordre = max(0, obj.ordre - 1)
            obj.save(update_fields=["ordre"])
        self.message_user(request, "⬆ Filières déplacées vers le haut ✅")

    @admin.action(description="⬇ Déplacer vers le bas")
    def deplacer_vers_le_bas(self, request, queryset):
        for obj in queryset:
            obj.ordre += 1
            obj.save(update_fields=["ordre"])
        self.message_user(request, "⬇ Filières déplacées vers le bas ✅")


# ─── Niveau ─────────────────────────────────────────────────

@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    list_display = ("nom",)
    search_fields = ("nom",)


# ─── Matière ────────────────────────────────────────────────

@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ("nom", "filiere")
    list_filter = ("filiere",)
    search_fields = ("nom",)


# ─── Utilisateur ────────────────────────────────────────────

@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    list_display = ("user", "filiere", "niveau", "role", "email_verifie")
    list_filter = ("role", "filiere", "niveau")
    search_fields = ("user__username", "user__email")


# ─── Sujet ──────────────────────────────────────────────────

@admin.register(Sujet)
class SujetAdmin(admin.ModelAdmin):
    list_display = (
        "titre", "matiere", "niveau", "annee_academique",
        "statut", "vues", "telechargements",
    )
    list_filter = ("statut", "filiere", "niveau", "annee_academique")
    search_fields = ("titre", "description")


# ─── Téléchargement ─────────────────────────────────────────

@admin.register(Telechargement)
class TelechargementAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "sujet", "telecharge_le")
    search_fields = ("utilisateur__username",)


# ─── Activité ───────────────────────────────────────────────

@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "type", "cree_le")
    list_filter = ("type",)
    search_fields = ("utilisateur__username",)


# ─── Vérification ───────────────────────────────────────────

@admin.register(Verification)
class VerificationAdmin(admin.ModelAdmin):
    list_display = ("email", "code", "expire_le", "utilise")
    search_fields = ("email",)


# ─── Présence ───────────────────────────────────────────────

@admin.register(PresenceSession)
class PresenceSessionAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "debut", "fin", "secondes")


# ─── Push ───────────────────────────────────────────────────

@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "cree_le")
