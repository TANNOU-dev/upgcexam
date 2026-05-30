"""
Vues administration : dashboard, gestion CRUD, logs.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import ExtractWeekDay
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from ..decorators import email_verifie_required
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
from ..navigation import query_bibliotheque, safe_next_url
from ..utils import envoyer_code_verification, generer_code_verification
from .shared import _sujets_accessibles, _creer_code_verification, salutation
from .pwa import envoyer_notification_push


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

    stats = {
        "total_sujets": Sujet.objects.count(),
        "sujets_actifs": Sujet.objects.filter(statut="actif").count(),
        "sujets_en_attente": Sujet.objects.filter(statut="en_attente").count(),
        "sujets_restreints": Sujet.objects.filter(statut="actif", visibilite="restreint").count(),
        "total_utilisateurs": User.objects.count(),
        "total_telechargements": Telechargement.objects.count(),
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
    mapping = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}

    # Temps réel passé (en secondes) depuis PresenceSession
    cette_semaine = timezone.now() - timezone.timedelta(days=7)
    sessions_semaine = PresenceSession.objects.filter(
        utilisateur_id=user_id, debut__gte=cette_semaine
    ).annotate(jour_sem=ExtractWeekDay("debut"))

    valeurs = [0] * 7
    if sessions_semaine.exists():
        for s in sessions_semaine:
            idx = mapping.get(s.jour_sem, 0)
            valeurs[idx] += s.secondes

    # Échelle dynamique : le pic de la semaine = 100%
    max_secondes_vu = max(valeurs) if valeurs else 0
    if max_secondes_vu <= 0:
        max_echelle = 3600  # 1h minimum
    else:
        max_echelle = min(((max_secondes_vu // 3600) + 1) * 3600, 10 * 3600)

    valeurs_pct = [
        min(max(round(v / max_echelle * 100, 1), 10 if v > 0 else 0), 100)
        for v in valeurs
    ]

    max_h = max_echelle // 3600
    pas = max(1, max_h // 4)
    labels_num = list(range(0, max_h + 1, pas))
    if labels_num[-1] != max_h:
        labels_num.append(max_h)
    echelle_labels = [f"{h}h" for h in reversed(labels_num)]

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
    activite = list(zip(jours, valeurs_pct, temps_format))

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
            "echelle_labels": echelle_labels,
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


@login_required
def admin_utilisateurs(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        try:
            target = User.objects.get(id=user_id) if user_id else None
        except User.DoesNotExist:
            messages.error(request, "Utilisateur introuvable.")
            return redirect("admin_utilisateurs")

        if action == "toggle_staff" and target:
            if target != request.user:
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
def admin_filieres(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

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
        Filiere.objects.annotate(nb_sujets=Count("sujets"), nb_etudiants=Count("etudiants"))
        .order_by("code")
    )
    return render(request, "core/admin/filieres.html", {"filieres": filieres})


@login_required
def admin_matieres(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

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
def admin_niveaux(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

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
def admin_logs(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

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
def admin_sujets(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

    if request.method == "POST":
        action = request.POST.get("action")
        sujet_id = request.POST.get("sujet_id")
        sujets_ids = request.POST.getlist("sujets_ids") or []

        if action in ("valider", "archiver", "reactiver", "supprimer", "rendre_visible", "restreindre"):
            if not sujets_ids and not sujet_id:
                messages.error(request, "Aucun sujet sélectionné.")
                return redirect("admin_sujets")

            ids_list = sujets_ids or [sujet_id]
            ids_list = [int(x) for x in ids_list if x]

            if action == "valider":
                updated = Sujet.objects.filter(id__in=ids_list, statut="en_attente").update(statut="actif")
                for sid in ids_list:
                    Activite.objects.create(
                        utilisateur=request.user,
                        type="validation",
                        sujet_id=sid,
                        description=f"Validation du sujet #{sid}",
                    )
                messages.success(request, f"{updated} sujet(s) validé(s) et publié(s).")
            elif action == "archiver":
                updated = Sujet.objects.filter(id__in=ids_list, statut="actif").update(statut="archive")
                for sid in ids_list:
                    Activite.objects.create(
                        utilisateur=request.user,
                        type="archivage",
                        sujet_id=sid,
                        description=f"Archivage du sujet #{sid}",
                    )
                messages.success(request, f"{updated} sujet(s) archivé(s).")
            elif action == "reactiver":
                updated = Sujet.objects.filter(id__in=ids_list, statut="archive").update(statut="actif")
                for sid in ids_list:
                    Activite.objects.create(
                        utilisateur=request.user,
                        type="validation",
                        sujet_id=sid,
                        description=f"Réactivation du sujet #{sid}",
                    )
                messages.success(request, f"{updated} sujet(s) réactivé(s).")
            elif action == "rendre_visible":
                updated = Sujet.objects.filter(id__in=ids_list, visibilite="restreint").update(visibilite="visible")
                for sid in ids_list:
                    Activite.objects.create(
                        utilisateur=request.user,
                        type="validation",
                        sujet_id=sid,
                        description=f"Visibilité activée sur le sujet #{sid}",
                    )
                messages.success(request, f"{updated} sujet(s) désormais visible(s) par tous.")
            elif action == "restreindre":
                updated = Sujet.objects.filter(id__in=ids_list, visibilite="visible").update(visibilite="restreint")
                for sid in ids_list:
                    Activite.objects.create(
                        utilisateur=request.user,
                        type="archivage",
                        sujet_id=sid,
                        description=f"Visibilité restreinte sur le sujet #{sid}",
                    )
                messages.success(request, f"{updated} sujet(s) passé(s) en accès restreint.")
            elif action == "supprimer":
                n = len(ids_list)
                for sid in ids_list:
                    Activite.objects.create(
                        utilisateur=request.user,
                        type="archivage",
                        description=f"Suppression du sujet #{sid}",
                    )
                Sujet.objects.filter(id__in=ids_list).delete()
                messages.success(request, f"{n} sujet(s) supprimé(s) définitivement.")
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
            "annees": Sujet.objects.values_list("annee_academique", flat=True)
            .distinct()
            .order_by("-annee_academique"),
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
def admin_voir_sujet_pdf(request, sujet_id):
    if not request.user.is_staff:
        raise Http404()
    sujet = get_object_or_404(Sujet, id=sujet_id)
    return FileResponse(sujet.fichier_pdf.open("rb"), filename=f"{sujet.titre}.pdf")


@login_required
def admin_verifications(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "renvoyer":
            email = request.POST.get("email", "").strip()
            if email and User.objects.filter(email=email).exists():
                user = User.objects.get(email=email)
                try:
                    _creer_code_verification(email, request)
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
