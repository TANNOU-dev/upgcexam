"""
Vues administration : dashboard, gestion CRUD, logs.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission, User
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Prefetch, Q, Sum
from django.db.models.functions import ExtractWeekDay
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from ..decorators import email_verifie_required, staff_required, superuser_required
from ..models import (
    Activite,
    Filiere,
    Matiere,
    Niveau,
    PresenceSession,
    Sujet,
    Telechargement,
    Utilisateur,
    Verification,
)
from .pwa import envoyer_notification_push
from .shared import _sujets_accessibles, creer_code_verification, salutation, _annees_actives


@login_required
@staff_required
def admin_dashboard(request):

    stats = {
        "total_sujets": Sujet.objects.count(),
        "sujets_actifs": Sujet.objects.filter(statut="actif").count(),
        "sujets_en_attente": Sujet.objects.filter(statut="en_attente").count(),
        "sujets_restreints": Sujet.objects.filter(statut="actif", visibilite="restreint").count(),
        "total_utilisateurs": User.objects.count(),
        "total_telechargements": Telechargement.objects.count(),
        "total_filieres": Filiere.objects.count(),
        "total_matieres": Matiere.objects.count(),
        "total_niveaux": Niveau.objects.count(),
        "total_groupes": Group.objects.count(),
        "total_activites": Activite.objects.count(),
        "total_sessions_presence": PresenceSession.objects.count(),
        "total_verifications": Verification.objects.count(),
        "total_codes_actifs": Verification.objects.filter(
            utilise=False, expire_le__gte=timezone.now()
        ).count(),
    }

    # ---- Statistiques de présence agrégées (tous les utilisateurs) ----
    aujourdhui = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cette_semaine = aujourdhui - timezone.timedelta(days=7)

    sessions_aujourdhui = PresenceSession.objects.filter(debut__gte=aujourdhui)
    sessions_semaine = PresenceSession.objects.filter(debut__gte=cette_semaine)

    actifs_ajd = (
        sessions_aujourdhui.values("utilisateur").distinct().count()
    )
    actifs_semaine = (
        sessions_semaine.values("utilisateur").distinct().count()
    )

    temps_total_ajd = sessions_aujourdhui.aggregate(total=Sum("secondes"))["total"] or 0
    temps_total_semaine = sessions_semaine.aggregate(total=Sum("secondes"))["total"] or 0

    def ft(sec):
        h, m = sec // 3600, (sec % 3600) // 60
        if h > 0: return f"{h}h{' ' + str(m) + 'min' if m > 0 else ''}"
        return f"{m} min" if m > 0 else "—"

    # Top étudiants cette semaine
    top_etudiants = (
        sessions_semaine
        .values("utilisateur", "utilisateur__username")
        .annotate(total=Sum("secondes"))
        .order_by("-total")[:10]
    )
    for e in top_etudiants:
        e["temps"] = ft(e["total"])

    # Barres d'activité hebdo agrégées (tous utilisateurs)
    mapping = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    jours_agg = sessions_semaine.annotate(
        jour_sem=ExtractWeekDay("debut")
    ).values("jour_sem").annotate(
        total=Sum("secondes")
    ).order_by("jour_sem")

    valeurs_hebdo = [0] * 7
    for j in jours_agg:
        valeurs_hebdo[mapping.get(j["jour_sem"], 0)] = j["total"]

    MAX_PX = 140
    MAX_ECHELLE = max(max(valeurs_hebdo), 600) if any(valeurs_hebdo) else 600
    jours_noms = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    activite_hebdo = []
    for i, val in enumerate(valeurs_hebdo):
        hauteur = round(val / MAX_ECHELLE * MAX_PX) if MAX_ECHELLE > 0 else 0
        activite_hebdo.append({
            "jour": jours_noms[i],
            "secondes": val,
            "temps": ft(val),
            "hauteur_px": min(hauteur, MAX_PX),
        })

    activite_stats = {
        "actifs_ajd": actifs_ajd,
        "actifs_semaine": actifs_semaine,
        "temps_total_ajd": ft(temps_total_ajd),
        "temps_total_semaine": ft(temps_total_semaine),
        "top_etudiants": top_etudiants,
        "activite_hebdo": activite_hebdo,
    }

    sujets_recents = Sujet.objects.select_related("filiere", "publie_par").order_by("-cree_le")[:10]
    utilisateurs_recents = User.objects.select_related("profil").order_by("-date_joined")[:10]
    sujets_en_attente = (
        Sujet.objects.filter(statut="en_attente")
        .select_related("filiere", "matiere", "niveau", "publie_par")
        .order_by("-cree_le")[:10]
    )

    if request.method == "POST" and "valider_sujet" in request.POST:
        sujet_id = request.POST.get("sujet_id")
        try:
            sujet = Sujet.objects.get(id=sujet_id, statut="en_attente")
            sujet.statut = "actif"
            sujet.save()
            # Notifier l'étudiant qui a soumis le sujet
            if sujet.publie_par and sujet.publie_par != request.user:
                envoyer_notification_push(
                    sujet.publie_par,
                    "✅ Sujet validé",
                    f"Votre sujet « {sujet.titre} » a été validé et publié.",
                    url=reverse("detail_sujet", args=[sujet.id]),
                )
            messages.success(request, f"Sujet « {sujet.titre} » validé et publié.")
        except Sujet.DoesNotExist:
            messages.error(request, "Sujet introuvable ou déjà traité.")
        return redirect("admin_dashboard")

    return render(
        request,
        "core/admin_dashboard.html",
        {
            "stats": stats,
            "sujets_recents": sujets_recents,
            "utilisateurs_recents": utilisateurs_recents,
            "sujets_en_attente": sujets_en_attente,
            "activite_stats": activite_stats,
        },
    )


@email_verifie_required
def tableau_de_bord(request):
    user_id = request.user.id
    sujets_vus = Activite.objects.filter(utilisateur_id=user_id, type="consultation").count()
    pdfs_telecharges = Telechargement.objects.filter(utilisateur_id=user_id).count()
    stats = {
        "sujets_vus": sujets_vus,
        "pdfs_telecharges": pdfs_telecharges,
        "matieres": Matiere.objects.count(),
        "filieres": Filiere.objects.count(),
    }

    progressions = []
    couleurs = ["#0037B0", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6"]
    # Optimisation N+1 : stats par filière en 2 queries au lieu de N
    top_filieres = list(Filiere.objects.all()[:5])
    filiere_ids = [f.id for f in top_filieres]
    sujets_par_filiere = dict(
        Sujet.objects.filter(filiere_id__in=filiere_ids, statut="actif")
        .values_list("filiere_id")
        .annotate(total=Count("id"))
    )
    sujets_vus_par_filiere = dict(
        Activite.objects.filter(
            utilisateur_id=user_id, sujet__filiere_id__in=filiere_ids, type="consultation"
        )
        .values("sujet__filiere_id")
        .annotate(total=Count("sujet_id", distinct=True))
        .values_list("sujet__filiere_id", "total")
    )
    for i, filiere in enumerate(top_filieres):
        total_sujets = sujets_par_filiere.get(filiere.id, 0)
        vus = sujets_vus_par_filiere.get(filiere.id, 0) if total_sujets > 0 else 0
        if total_sujets > 0:
            pct = min(int(vus * 100 / total_sujets), 100)
        else:
            pct = 0
        progressions.append(
            {"nom": filiere.nom, "pourcentage": pct, "couleur": couleurs[i % len(couleurs)]}
        )

    jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    valeurs = _temps_activite(user_id)["valeurs"]

    # Échelle FIXE
    # Échelle FIXE à 3h (10800s) : visible dès 15min, plein à 3h
    # 15min→12px  30min→27px  1h→53px  2h→107px  3h→160px
    MAX_ECHELLE = 18000  # 5 heures en secondes
    BAR_MAX_PX = 160

    valeurs_pct = [
        min(round(v / MAX_ECHELLE * 100, 1), 100)
        for v in valeurs
    ]
    hauteurs_px = [
        max(round(v / MAX_ECHELLE * BAR_MAX_PX), 0)
        for v in valeurs
    ]

    temps_format = []
    for v in valeurs:
        heures = v // 3600
        minutes = (v % 3600) // 60
        if heures > 0:
            temps_format.append(f"{heures}h{minutes:02d}")
        elif minutes > 0:
            temps_format.append(f"{minutes}min")
        elif v > 0:
            temps_format.append(f"{v}s")
        else:
            temps_format.append("—")
    activite = list(zip(jours, valeurs_pct, hauteurs_px, temps_format))

    total_secondes = sum(valeurs)
    aujourdhui_idx = timezone.now().weekday()
    jours_actifs = sum(1 for v in valeurs if v > 0)
    moyenne_sec = total_secondes // max(jours_actifs, 1)

    def formater_temps(sec):
        h = sec // 3600
        m = (sec % 3600) // 60
        if h > 0:
            return f"{h}h {m:02d}" if m > 0 else f"{h}h"
        elif m > 0:
            return f"{m} min"
        elif sec > 0:
            return f"{sec} s"
        return "—"

    temps_aujourd_hui = formater_temps(valeurs[aujourdhui_idx])
    moyenne_jour = formater_temps(moyenne_sec)
    total_semaine = formater_temps(total_secondes)
    if total_semaine != "—":
        total_semaine = f"{total_semaine}"
    moyenne_semaine = formater_temps(total_secondes)
    jours_noms = ["LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE"]
    aujourdhui_nom = jours_noms[aujourdhui_idx]

    sujets_recommandes = []
    for sujet in _sujets_accessibles(request).order_by("-vues")[:3]:
        sujets_recommandes.append({"titre": sujet.titre, "annee": sujet.annee_academique})

    activites_recentes = []
    for act in Activite.objects.filter(utilisateur_id=user_id).order_by("-cree_le")[:5]:
        depuis = timezone.now() - act.cree_le
        if depuis.total_seconds() < 60:
            temps = "Il y a quelques secondes"
        elif depuis.total_seconds() < 3600:
            temps = f"Il y a {int(depuis.total_seconds() // 60)} minutes"
        elif depuis.total_seconds() < 86400:
            temps = f"Il y a {int(depuis.total_seconds() // 3600)} heures"
        else:
            temps = f"Il y a {int(depuis.total_seconds() // 86400)} jours"
        activites_recentes.append(
            {
                "type": act.type,
                "description": act.description
                or f"{dict(Activite.TYPE_CHOICES).get(act.type, act.type)}",
                "temps": temps,
            }
        )

    return render(
        request,
        "core/tableau_de_bord.html",
        {
            "stats": stats,
            "progressions": progressions,
            "activite": activite,
            "total_semaine": total_semaine,
            "temps_aujourd_hui": temps_aujourd_hui,
            "moyenne_jour": moyenne_jour,
            "moyenne_semaine": moyenne_semaine,
            "aujourdhui_nom": aujourdhui_nom,
            "sujets_recommandes": sujets_recommandes,
            "activites_recentes": activites_recentes,
            "salutation": salutation(),
        },
    )


def _temps_activite(utilisateur_id):
    """Calcule le temps d'activité par jour pour un utilisateur."""
    mapping = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    cette_semaine = timezone.now() - timezone.timedelta(days=7)
    sessions = PresenceSession.objects.filter(
        utilisateur_id=utilisateur_id, debut__gte=cette_semaine
    ).annotate(jour_sem=ExtractWeekDay("debut"))
    valeurs = [0] * 7
    for s in sessions:
        valeurs[mapping.get(s.jour_sem, 0)] += s.secondes
    return {"valeurs": valeurs}


@login_required
def mon_activite_json(request):
    """Retourne les données d'activité en JSON (rafraîchissement AJAX)."""
    data = _temps_activite(request.user.id)
    valeurs = data["valeurs"]
    aujourdhui_idx = timezone.now().weekday()
    MAX_ECHELLE = 18000
    BAR_MAX_PX = 160

    def ft(sec):
        h, m = sec // 3600, (sec % 3600) // 60
        if h > 0: return f"{h}h {m:02d}" if m > 0 else f"{h}h"
        if m > 0: return f"{m} min"
        if sec > 0: return f"{sec} s"
        return "—"

    return JsonResponse({
        "secondes": valeurs,
        "pourcentages": [min(round(v / MAX_ECHELLE * 100, 1), 100) for v in valeurs],
        "hauteurs_px": [max(round(v / MAX_ECHELLE * BAR_MAX_PX), 0) for v in valeurs],
        "aujourd_hui": ft(valeurs[aujourdhui_idx]),
        "total_semaine": ft(sum(valeurs)),
    })


def _parse_subject_ids(values):
    """Convertit une sélection de sujets en identifiants entiers uniques."""
    subject_ids = []
    for value in values:
        try:
            subject_id = int(value)
        except (TypeError, ValueError):
            continue
        if subject_id not in subject_ids:
            subject_ids.append(subject_id)
    return subject_ids


def _update_subjects_with_activity(user, subject_ids, filters, changes, activity_type, label):
    """Met à jour des sujets existants et journalise uniquement les lignes modifiées."""
    updated_ids = list(
        Sujet.objects.filter(id__in=subject_ids, **filters).values_list("id", flat=True)
    )
    Sujet.objects.filter(id__in=updated_ids).update(**changes)
    Activite.objects.bulk_create(
        [
            Activite(
                utilisateur=user,
                type=activity_type,
                sujet_id=subject_id,
                description=f"{label} du sujet #{subject_id}",
            )
            for subject_id in updated_ids
        ]
    )
    return len(updated_ids)


@login_required
@staff_required
def admin_utilisateurs(request):

    if request.method == "POST":
        if not request.user.is_superuser:
            messages.error(request, "Action réservée aux superutilisateurs.")
            return redirect("admin_utilisateurs")

        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        try:
            target = User.objects.get(id=user_id) if user_id else None
        except User.DoesNotExist:
            messages.error(request, "Utilisateur introuvable.")
            return redirect("admin_utilisateurs")

        if action == "toggle_staff" and target:
            if not request.user.is_superuser:
                messages.error(request, "Action réservée aux superutilisateurs.")
            elif target != request.user:
                target.is_staff = not target.is_staff
                target.save()
                messages.success(request, f"Rôle de {target.username} mis à jour.")
            else:
                messages.error(request, "Vous ne pouvez pas modifier votre propre rôle.")

        elif action == "toggle_active" and target:
            if target != request.user:
                target.is_active = not target.is_active
                target.save()
                status = "activé" if target.is_active else "désactivé"
                messages.success(request, f"Compte de {target.username} {status}.")
            else:
                messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")

        elif action == "delete_user" and target:
            if target != request.user and not target.is_superuser:
                username = target.username
                target.delete()
                messages.success(request, f"Utilisateur {username} supprimé.")
            else:
                messages.error(request, "Impossible de supprimer cet utilisateur.")

        return redirect("admin_utilisateurs")

    utilisateurs = User.objects.select_related("profil").order_by("-date_joined")
    return render(
        request,
        "core/admin/utilisateurs.html",
        {
            "utilisateurs": utilisateurs,
            "total": utilisateurs.count(),
            "actifs": utilisateurs.filter(is_active=True).count(),
            "staff": utilisateurs.filter(is_staff=True).count(),
        },
    )


@login_required
@staff_required
def admin_filieres(request):

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "ajouter":
            nom = request.POST.get("nom", "").strip()
            code = request.POST.get("code", "").strip().upper()
            if nom and code:
                Filiere.objects.create(nom=nom, code=code)
                messages.success(request, f"Filière {code} - {nom} ajoutée.")
            else:
                messages.error(request, "Nom et code requis.")
        elif action == "modifier":
            fid = request.POST.get("filiere_id")
            nom = request.POST.get("nom", "").strip()
            code = request.POST.get("code", "").strip().upper()
            if fid and nom and code:
                Filiere.objects.filter(id=fid).update(nom=nom, code=code)
                messages.success(request, "Filière modifiée.")
        elif action == "supprimer":
            fid = request.POST.get("filiere_id")
            if fid:
                Filiere.objects.filter(id=fid).delete()
                messages.success(request, "Filière supprimée.")
        return redirect("admin_filieres")

    filieres = (
        Filiere.objects.annotate(
            nb_sujets=Count("sujets", distinct=True),
            nb_etudiants=Count("etudiants", distinct=True),
        )
        .order_by("code")
    )
    return render(request, "core/admin/filieres.html", {"filieres": filieres})


@login_required
@staff_required
def admin_matieres(request):

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "ajouter":
            nom = request.POST.get("nom", "").strip()
            filiere_id = request.POST.get("filiere_id")
            if nom and filiere_id:
                Matiere.objects.create(nom=nom, filiere_id=filiere_id)
                messages.success(request, f"Matière {nom} ajoutée.")
            else:
                messages.error(request, "Nom et filière requis.")
        elif action == "supprimer":
            mid = request.POST.get("matiere_id")
            if mid:
                Matiere.objects.filter(id=mid).delete()
                messages.success(request, "Matière supprimée.")
        return redirect("admin_matieres")

    matieres = (
        Matiere.objects.select_related("filiere")
        .annotate(nb_sujets=Count("sujets"))
        .order_by("filiere__code", "nom")
    )
    return render(
        request,
        "core/admin/matieres.html",
        {"matieres": matieres, "filieres": Filiere.objects.all()},
    )


@login_required
@staff_required
def admin_niveaux(request):

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "ajouter":
            nom = request.POST.get("nom", "").strip()
            if nom:
                Niveau.objects.create(nom=nom)
                messages.success(request, f"Niveau {nom} ajouté.")
        elif action == "supprimer":
            nid = request.POST.get("niveau_id")
            if nid:
                Niveau.objects.filter(id=nid).delete()
                messages.success(request, "Niveau supprimé.")
        return redirect("admin_niveaux")

    niveaux = Niveau.objects.annotate(nb_sujets=Count("sujets")).order_by("nom")
    return render(request, "core/admin/niveaux.html", {"niveaux": niveaux})


@login_required
@staff_required
def admin_logs(request):

    activites = Activite.objects.select_related("utilisateur", "sujet__matiere").order_by("-cree_le")[:100]
    telechargements = (
        Telechargement.objects.select_related("utilisateur", "sujet__matiere")
        .order_by("-telecharge_le")[:100]
    )
    return render(
        request,
        "core/admin/logs.html",
        {"activites": activites, "telechargements": telechargements},
    )


@login_required
@staff_required
def admin_sujets(request):

    if request.method == "POST":
        action = request.POST.get("action")
        sujet_id = request.POST.get("sujet_id")
        sujets_ids = request.POST.getlist("sujets_ids") or []

        if action in ("valider", "archiver", "reactiver", "supprimer", "rendre_visible", "restreindre"):
            if not sujets_ids and not sujet_id:
                messages.error(request, "Aucun sujet sélectionné.")
                return redirect("admin_sujets")

            ids_list = _parse_subject_ids(sujets_ids or [sujet_id])
            if not ids_list:
                messages.error(request, "Aucun sujet valide sélectionné.")
                return redirect("admin_sujets")

            if action == "valider":
                sujets_a_valider = list(
                    Sujet.objects.filter(id__in=ids_list, statut="en_attente")
                    .select_related("publie_par")
                )
                Sujet.objects.filter(id__in=[s.id for s in sujets_a_valider]).update(statut="actif")
                for sujet_valide in sujets_a_valider:
                    Activite.objects.create(
                        utilisateur=request.user,
                        type="validation",
                        sujet=sujet_valide,
                        description=f"Validation du sujet #{sujet_valide.id}",
                    )
                    # Notifier l'étudiant
                    if sujet_valide.publie_par and sujet_valide.publie_par != request.user:
                        envoyer_notification_push(
                            sujet_valide.publie_par,
                            "✅ Sujet validé",
                            f"Votre sujet « {sujet_valide.titre} » a été validé et publié sur la bibliothèque.",
                            url=reverse("detail_sujet", args=[sujet_valide.id]),
                        )
                messages.success(request, f"{len(sujets_a_valider)} sujet(s) validé(s) et publié(s).")
            elif action == "archiver":
                updated = _update_subjects_with_activity(
                    request.user,
                    ids_list,
                    {"statut": "actif"},
                    {"statut": "archive"},
                    "archivage",
                    "Archivage",
                )
                messages.success(request, f"{updated} sujet(s) archivé(s).")
            elif action == "reactiver":
                updated = _update_subjects_with_activity(
                    request.user,
                    ids_list,
                    {"statut": "archive"},
                    {"statut": "actif"},
                    "validation",
                    "Réactivation",
                )
                messages.success(request, f"{updated} sujet(s) réactivé(s).")
            elif action == "rendre_visible":
                updated = _update_subjects_with_activity(
                    request.user,
                    ids_list,
                    {"visibilite": "restreint"},
                    {"visibilite": "visible"},
                    "validation",
                    "Activation de la visibilité",
                )
                messages.success(request, f"{updated} sujet(s) désormais visible(s) par tous.")
            elif action == "restreindre":
                updated = _update_subjects_with_activity(
                    request.user,
                    ids_list,
                    {"visibilite": "visible"},
                    {"visibilite": "restreint"},
                    "archivage",
                    "Restriction de la visibilité",
                )
                messages.success(request, f"{updated} sujet(s) passé(s) en accès restreint.")
            elif action == "supprimer":
                existing_ids = list(
                    Sujet.objects.filter(id__in=ids_list).values_list("id", flat=True)
                )
                Activite.objects.bulk_create(
                    [
                        Activite(
                            utilisateur=request.user,
                            type="archivage",
                            description=f"Suppression du sujet #{sid}",
                        )
                        for sid in existing_ids
                    ]
                )
                Sujet.objects.filter(id__in=existing_ids).delete()
                messages.success(request, f"{len(existing_ids)} sujet(s) supprimé(s) définitivement.")
        else:
            if sujet_id:
                sujet = get_object_or_404(Sujet, id=sujet_id)
                if sujet.visibilite == "restreint":
                    Sujet.objects.filter(id=sujet_id).update(visibilite="visible")
                    messages.success(request, "Sujet désormais visible par tous.")
                else:
                    Sujet.objects.filter(id=sujet_id).update(visibilite="restreint")
                    messages.success(request, "Sujet passé en accès restreint.")

        return redirect("admin_sujets")

    filtre_statut = request.GET.get("statut", "")
    filtre_filiere = request.GET.get("filiere", "")
    filtre_annee = request.GET.get("annee", "")
    filtre_visibilite = request.GET.get("visibilite", "")
    recherche = request.GET.get("q", "").strip()

    sujets = Sujet.objects.select_related("filiere", "matiere", "niveau", "publie_par").order_by("-cree_le")
    if recherche:
        sujets = sujets.filter(
            Q(titre__icontains=recherche)
            | Q(matiere__nom__icontains=recherche)
            | Q(publie_par__username__icontains=recherche)
            | Q(publie_par__email__icontains=recherche)
        )
    if filtre_statut:
        sujets = sujets.filter(statut=filtre_statut)
    if filtre_filiere:
        sujets = sujets.filter(filiere_id=filtre_filiere)
    if filtre_annee:
        sujets = sujets.filter(annee_academique=filtre_annee)
    if filtre_visibilite:
        sujets = sujets.filter(visibilite=filtre_visibilite)

    sujets_page = Paginator(sujets, 25).get_page(request.GET.get("page", 1))

    return render(
        request,
        "core/admin/sujets.html",
        {
            "sujets": sujets_page,
            "filieres": Filiere.objects.all(),
            "annees": _annees_actives(Sujet.objects.all()),
            "filtre_statut": filtre_statut,
            "filtre_filiere": filtre_filiere,
            "filtre_annee": filtre_annee,
            "filtre_visibilite": filtre_visibilite,
            "recherche": recherche,
            "stats": {
                "total": Sujet.objects.count(),
                "actifs": Sujet.objects.filter(statut="actif").count(),
                "en_attente": Sujet.objects.filter(statut="en_attente").count(),
                "archives": Sujet.objects.filter(statut="archive").count(),
                "restreints": Sujet.objects.filter(statut="actif", visibilite="restreint").count(),
            },
        },
    )


@login_required
@staff_required
def admin_voir_sujet_pdf(request, sujet_id):
    sujet = get_object_or_404(Sujet, id=sujet_id)
    return FileResponse(sujet.fichier_pdf.open("rb"), filename=f"{sujet.titre}.pdf")


@login_required
@staff_required
def admin_presences(request):
    """Liste tous les étudiants avec leur temps de connexion."""

    aujourdhui = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cette_semaine = aujourdhui - timezone.timedelta(days=7)

    # Agrégation : temps total et dernière activité par utilisateur
    aggs = (
        PresenceSession.objects.filter(debut__gte=cette_semaine)
        .values("utilisateur")
        .annotate(
            total=Sum("secondes"),
            derniere_activite=Max("fin"),
            jours_actifs=Count("id", distinct=True),
        )
        .order_by("-total")
    )

    # Tous les utilisateurs avec ou sans activité cette semaine
    utilisateurs_data = []
    aggs_map = {a["utilisateur"]: a for a in aggs}
    for u in User.objects.all().order_by("-date_joined"):
        data = aggs_map.get(u.id)
        total_sec = data["total"] if data else 0
        h, m = total_sec // 3600, (total_sec % 3600) // 60
        if h > 0:
            temps_str = f"{h}h {m:02d}" if m > 0 else f"{h}h"
        elif m > 0:
            temps_str = f"{m} min"
        elif total_sec > 0:
            temps_str = f"{total_sec} s"
        else:
            temps_str = "—"

        dernier = data["derniere_activite"] if data else None
        if dernier:
            depuis = timezone.now() - dernier
            if depuis.total_seconds() < 3600:
                dernier_str = f"Il y a {int(depuis.total_seconds() // 60)} min"
            else:
                dernier_str = f"Il y a {int(depuis.total_seconds() // 3600)}h"
        else:
            dernier_str = "—"

        utilisateurs_data.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_staff": u.is_staff,
            "temps": temps_str,
            "secondes": total_sec,
            "derniere_activite": dernier_str,
        })

    # Tri par temps décroissant (les inactifs à la fin)
    utilisateurs_data.sort(key=lambda x: (x["secondes"] == 0, -x["secondes"]))

    paginator = Paginator(utilisateurs_data, 25)
    page = request.GET.get("page", 1)
    page_obj = paginator.get_page(page)

    return render(
        request,
        "core/admin_presences.html",
        {
            "page_obj": page_obj,
            "total_utilisateurs": User.objects.count(),
            "actifs_semaine": sum(1 for u in utilisateurs_data if u["secondes"] > 0),
        },
    )


@login_required
@staff_required
def admin_verifications(request):

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "renvoyer":
            email = request.POST.get("email", "").strip()
            if email and User.objects.filter(email=email).exists():
                user = User.objects.get(email=email)
                try:
                    creer_code_verification(email, request)
                except Exception:
                    messages.error(request, "Échec de l'envoi du code par email.")
                    return redirect("admin_verifications")
                if hasattr(user, "profil"):
                    user.profil.email_verifie = False
                    user.profil.save()
                messages.success(request, f"Un nouveau code a été envoyé à {email}.")
            else:
                messages.error(request, "Email invalide ou inconnu.")
        elif action == "forcer_verification":
            user_id = request.POST.get("user_id")
            if user_id:
                user = get_object_or_404(User, id=user_id)
                profil, _ = Utilisateur.objects.get_or_create(user=user)
                profil.email_verifie = True
                profil.save()
                messages.success(request, f"Email de {user.username} vérifié manuellement.")
        return redirect("admin_verifications")

    codes = Verification.objects.filter(utilise=False, expire_le__gte=timezone.now()).order_by("-expire_le")
    non_verifies = (
        User.objects.filter(profil__email_verifie=False)
        .select_related("profil")
        .distinct()
        .order_by("-date_joined")
    )
    return render(
        request,
        "core/admin/verifications.html",
        {"codes": codes, "non_verifies": non_verifies},
    )


# ============================================================
# Groupes (auth.Group)
# ============================================================
@superuser_required
def admin_groupes(request):
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "ajouter":
            nom = request.POST.get("nom", "").strip()
            if nom:
                Group.objects.create(name=nom)
                messages.success(request, f"Groupe « {nom} » créé.")
            else:
                messages.error(request, "Nom du groupe requis.")

        elif action == "supprimer":
            gid = request.POST.get("groupe_id")
            if gid:
                try:
                    groupe = Group.objects.get(id=gid)
                    nom = groupe.name
                    groupe.delete()
                    messages.success(request, f"Groupe « {nom} » supprimé.")
                except Group.DoesNotExist:
                    messages.error(request, "Groupe introuvable.")

        elif action == "renommer":
            gid = request.POST.get("groupe_id")
            nom = request.POST.get("nom", "").strip()
            if gid and nom:
                try:
                    groupe = Group.objects.get(id=gid)
                    groupe.name = nom
                    groupe.save()
                    messages.success(request, "Groupe renommé.")
                except Group.DoesNotExist:
                    messages.error(request, "Groupe introuvable.")

        elif action == "modifier_permissions":
            gid = request.POST.get("groupe_id")
            if gid:
                groupe = get_object_or_404(Group, id=gid)
                perm_ids = request.POST.getlist("permissions")
                groupe.permissions.set(perm_ids)
                messages.success(request, f"Permissions de « {groupe.name} » mises à jour.")

        elif action == "ajouter_utilisateur":
            gid = request.POST.get("groupe_id")
            uid = request.POST.get("user_id")
            if gid and uid:
                try:
                    groupe = Group.objects.get(id=gid)
                    user = User.objects.get(id=uid)
                    user.groups.add(groupe)
                    messages.success(request, f"{user.username} ajouté au groupe « {groupe.name} ».")
                except (Group.DoesNotExist, User.DoesNotExist):
                    messages.error(request, "Erreur.")

        elif action == "retirer_utilisateur":
            gid = request.POST.get("groupe_id")
            uid = request.POST.get("user_id")
            if gid and uid:
                try:
                    groupe = Group.objects.get(id=gid)
                    user = User.objects.get(id=uid)
                    user.groups.remove(groupe)
                    messages.success(request, f"{user.username} retiré du groupe « {groupe.name} ».")
                except (Group.DoesNotExist, User.DoesNotExist):
                    messages.error(request, "Erreur.")

        return redirect("admin_groupes")

    groupes = (
        Group.objects.annotate(nb_utilisateurs=Count("user", distinct=True))
        .prefetch_related(
            "permissions",
            Prefetch("user_set", queryset=User.objects.order_by("username")),
        )
        .order_by("name")
    )
    permissions = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "codename"
    )
    utilisateurs = User.objects.order_by("username")

    # Grouper les permissions par app_label
    perms_par_app = {}
    for p in permissions:
        app = p.content_type.app_label
        if app not in perms_par_app:
            perms_par_app[app] = []
        perms_par_app[app].append(p)

    # Pour chaque groupe, récupérer les permissions et utilisateurs actuels
    groupes_data = []
    for g in groupes:
        groupes_data.append({
            "groupe": g,
            "permissions_ids": [permission.id for permission in g.permissions.all()],
            "utilisateurs": g.user_set.all(),
            "nb_utilisateurs": g.nb_utilisateurs,
        })

    return render(
        request,
        "core/admin/groupes.html",
        {
            "groupes_data": groupes_data,
            "permissions_par_app": perms_par_app,
            "utilisateurs": utilisateurs,
        },
    )


# ============================================================
# Abonnements Push
# ============================================================



# ============================================================
# Sessions de présence
# ============================================================
@login_required
@staff_required
def admin_sessions_presence(request):
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    sessions = PresenceSession.objects.select_related("utilisateur").order_by("-debut")

    # Stats
    total = sessions.count()
    aujourdhui = sessions.filter(debut__gte=today).count()
    moyenne = round(
        sessions.aggregate(avg=Avg("secondes"))["avg"] or 0
    )

    def ft(sec):
        h, m = sec // 3600, (sec % 3600) // 60
        return f"{h}h{m:02d}" if h > 0 else f"{m} min" if m > 0 else "—"

    paginator = Paginator(sessions, 50)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    for s in page_obj:
        s.temps_format = ft(s.secondes)

    return render(
        request,
        "core/admin/sessions_presence.html",
        {
            "page_obj": page_obj,
            "total": total,
            "aujourdhui": aujourdhui,
            "moyenne": ft(moyenne),
        },
    )
