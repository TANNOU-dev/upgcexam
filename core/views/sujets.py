"""
Vues publiques : accueil, bibliothèque/recherche, sujets (CRUD étudiant).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..decorators import email_verifie_required
from ..models import Activite, Filiere, Matiere, Niveau, Sujet, Telechargement
from ..navigation import (
    ctx_retour,
    query_bibliotheque,
    redirect_apres_sujet,
    safe_next_url,
)
from .shared import (
    _annees_actives,
    _get_sujet_modifiable,
    _sujets_accessibles,
    notifier_admins,
    valider_fichier_pdf,
)


def _catalog_ids_are_valid(filiere_id, niveau_id):
    """Vérifie et normalise les identifiants de catalogue reçus par formulaire."""
    try:
        filiere_id = int(filiere_id)
        niveau_id = int(niveau_id)
    except (TypeError, ValueError):
        return None
    if (
        not Filiere.objects.filter(id=filiere_id).exists()
        or not Niveau.objects.filter(id=niveau_id).exists()
    ):
        return None
    return filiere_id, niveau_id


def _academic_year_is_valid(value):
    """Accepte uniquement une année universitaire au format 2025-2026."""
    try:
        first_year, second_year = (int(part) for part in value.split("-"))
    except (TypeError, ValueError):
        return False
    return len(value) == 9 and second_year == first_year + 1


def accueil(request):
    sujets_qs = _sujets_accessibles(request)
    total_sujets = sujets_qs.count()
    total_filieres = Filiere.objects.count()
    annees_distinctes = sujets_qs.values_list("annee_academique", flat=True).distinct().count()

    sujets_populaires = sujets_qs.select_related("filiere", "matiere", "niveau").order_by("-vues")[:4]

    return render(
        request,
        "core/accueil.html",
        {
            "total_sujets": total_sujets,
            "total_filieres": total_filieres,
            "annees_distinctes": annees_distinctes,
            "sujets_populaires": sujets_populaires,
        },
    )


def bibliotheque(request):
    query = request.GET.get("q", "").strip()
    filiere_id = request.GET.get("filiere", "")
    matiere_id = request.GET.get("matiere", "")
    annee = request.GET.get("annee", "")

    sujets = _sujets_accessibles(request).order_by("-date_publication")

    if query:
        sujets = sujets.filter(
            Q(titre__icontains=query) | Q(description__icontains=query)
        )
    if filiere_id:
        try:
            sujets = sujets.filter(filiere_id=int(filiere_id))
        except ValueError:
            sujets = sujets.none()
    if matiere_id:
        try:
            sujets = sujets.filter(matiere_id=int(matiere_id))
        except ValueError:
            sujets = sujets.none()
    if annee:
        sujets = sujets.filter(annee_academique=annee)

    paginator = Paginator(sujets, 12)
    page = request.GET.get("page", 1)
    sujets_page = paginator.get_page(page)

    filieres = Filiere.objects.all()
    matieres = Matiere.objects.select_related("filiere").all()
    annees_list = _annees_actives(_sujets_accessibles(request))

    return render(
        request,
        "core/bibliotheque.html",
        {
            "sujets": sujets_page,
            "filieres": filieres,
            "matieres": matieres,
            "annees": annees_list,
            "query": query,
            "filiere_id": filiere_id,
            "matiere_id": matiere_id,
            "annee": annee,
            "filtres_qs": query_bibliotheque(request),
        },
    )


@email_verifie_required
def recherche(request):
    query = request.GET.get("q", "").strip()
    filieres = Filiere.objects.all()
    sujets_base = _sujets_accessibles(request)
    annees = _annees_actives(sujets_base)

    resultats = sujets_base.none()
    if query:
        resultats = sujets_base.filter(
            Q(titre__icontains=query)
            | Q(description__icontains=query)
            | Q(auteur_nom__icontains=query)
            | Q(matiere__nom__icontains=query)
        ).order_by("-vues")

    paginator = Paginator(resultats, 12)
    resultats_page = paginator.get_page(request.GET.get("page", 1))

    suggestions = sujets_base.order_by("-vues")[:4]
    docs_populaires = sujets_base.order_by("-vues")[:2]

    return render(
        request,
        "core/recherche.html",
        {
            "query": query,
            "resultats_page": resultats_page,
            "total_resultats": paginator.count,
            "filieres": filieres,
            "annees": annees,
            "suggestions": suggestions,
            "docs_populaires": docs_populaires,
        },
    )


@email_verifie_required
def ajouter_sujet(request):
    filieres = Filiere.objects.all()
    niveaux = Niveau.objects.all()
    annees = _annees_actives()

    if request.method == "POST":
        titre = request.POST.get("titre", "").strip()
        filiere_id = request.POST.get("filiere")
        nom_matiere = request.POST.get("matiere", "").strip()
        niveau_id = request.POST.get("niveau")
        annee_academique = request.POST.get("annee_academique", "").strip()
        fichier = request.FILES.get("fichier_pdf")

        if not all([titre, filiere_id, nom_matiere, niveau_id, annee_academique, fichier]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect("ajouter_sujet")
        catalog_ids = _catalog_ids_are_valid(filiere_id, niveau_id)
        if catalog_ids is None:
            messages.error(request, "Filière ou niveau invalide.")
            return redirect("ajouter_sujet")
        filiere_id, niveau_id = catalog_ids
        if (
            len(titre) > 200
            or len(nom_matiere) > 150
            or not _academic_year_is_valid(annee_academique)
        ):
            messages.error(request, "Les informations du sujet sont invalides.")
            return redirect("ajouter_sujet")
        ok, err = valider_fichier_pdf(fichier)
        if not ok:
            messages.error(request, err)
            return redirect("ajouter_sujet")
        else:
            matiere, _ = Matiere.objects.get_or_create(
                nom__iexact=nom_matiere,
                filiere_id=filiere_id,
                defaults={"nom": nom_matiere, "filiere_id": filiere_id},
            )
            sujet = Sujet.objects.create(
                titre=titre,
                filiere_id=filiere_id,
                matiere=matiere,
                niveau_id=niveau_id,
                annee_academique=annee_academique,
                fichier_pdf=fichier,
                publie_par=request.user,
                statut="en_attente",
                visibilite="visible",
            )
            Activite.objects.create(
                utilisateur=request.user,
                type="publication",
                sujet=sujet,
                description=f"Ajout du sujet : {titre}",
            )
            messages.success(request, "✅ Sujet ajouté avec succès ! En attente.")
            notifier_admins(
                "🆕 Nouveau sujet en attente",
                f"{titre} — {nom_matiere}",
                url=reverse("admin_sujets"),
            )
            return redirect_apres_sujet(request)

    return render(
        request,
        "core/ajouter_sujet.html",
        {
            "filieres": filieres,
            "niveaux": niveaux,
            "annees": annees,
            **ctx_retour(request),
        },
    )


@email_verifie_required
def modifier_sujet(request, sujet_id):
    sujet = _get_sujet_modifiable(request, sujet_id)

    filieres = Filiere.objects.all()
    niveaux = Niveau.objects.all()
    annees = _annees_actives()

    if request.method == "POST":
        if "archiver" in request.POST:
            if not request.user.is_staff:
                messages.error(request, "Seuls les administrateurs peuvent archiver un sujet.")
                return redirect_apres_sujet(request)
            sujet.statut = "archive"
            sujet.save()
            messages.success(request, "Sujet archivé avec succès.")
            return redirect_apres_sujet(request)

        titre = request.POST.get("titre", "").strip()
        filiere_id = request.POST.get("filiere")
        nom_matiere = request.POST.get("matiere", "").strip()
        niveau_id = request.POST.get("niveau")
        annee_academique = request.POST.get("annee_academique", "").strip()
        description = request.POST.get("description", "").strip()
        fichier = request.FILES.get("fichier_pdf")
        visibilite = request.POST.get("visibilite", "visible")

        if not all([titre, filiere_id, nom_matiere, niveau_id, annee_academique]):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
            return redirect("modifier_sujet", sujet_id=sujet.id)
        catalog_ids = _catalog_ids_are_valid(filiere_id, niveau_id)
        if catalog_ids is None:
            messages.error(request, "Filière ou niveau invalide.")
            return redirect("modifier_sujet", sujet_id=sujet.id)
        filiere_id, niveau_id = catalog_ids
        if (
            len(titre) > 200
            or len(nom_matiere) > 150
            or not _academic_year_is_valid(annee_academique)
        ):
            messages.error(request, "Les informations du sujet sont invalides.")
            return redirect("modifier_sujet", sujet_id=sujet.id)
        if request.user.is_staff and visibilite not in dict(Sujet.VISIBILITE_CHOICES):
            messages.error(request, "Visibilité invalide.")
            return redirect("modifier_sujet", sujet_id=sujet.id)

        if titre:
            sujet.titre = titre
        if filiere_id:
            sujet.filiere_id = filiere_id
        if nom_matiere:
            matiere, _ = Matiere.objects.get_or_create(
                nom__iexact=nom_matiere,
                filiere_id=filiere_id or sujet.filiere_id,
                defaults={"nom": nom_matiere, "filiere_id": filiere_id or sujet.filiere_id},
            )
            sujet.matiere = matiere
        if niveau_id:
            sujet.niveau_id = niveau_id
        if annee_academique:
            sujet.annee_academique = annee_academique
        sujet.description = description
        if fichier:
            ok, err = valider_fichier_pdf(fichier)
            if not ok:
                messages.error(request, err)
                return redirect("modifier_sujet", sujet_id=sujet.id)
            sujet.fichier_pdf = fichier

        # Seuls les admins peuvent changer la visibilite
        if request.user.is_staff:
            sujet.visibilite = visibilite
            sujet.save()
            messages.success(request, "Sujet modifié avec succès.")
            return redirect_apres_sujet(request, sujet=sujet, defaut="detail_sujet")

        # Pour un non-admin : ne remettre en attente QUE si des champs ont changé
        original = Sujet.objects.get(id=sujet.id)  # état avant modif
        a_change = (
            (titre and titre != original.titre)
            or (filiere_id and int(filiere_id) != original.filiere_id)
            or (
                nom_matiere
                and nom_matiere.lower() != (original.matiere.nom.lower() if original.matiere else "")
            )
            or (niveau_id and int(niveau_id) != original.niveau_id)
            or (annee_academique and annee_academique != original.annee_academique)
            or description != original.description
            or fichier is not None
        )

        if not a_change:
            messages.warning(request, "Aucune modification détectée.")
            return redirect_apres_sujet(request, sujet=sujet, defaut="detail_sujet")

        sujet.statut = "en_attente"
        sujet.save()
        messages.success(request, "✅ Modifications enregistrées. En attente de validation.")
        notifier_admins(
            "🔄 Sujet modifié — en attente",
            f"{sujet.titre} — {sujet.matiere.nom}",
            url=reverse("admin_sujets"),
        )
        return redirect(reverse("bibliotheque") + query_bibliotheque(request))

    retour = ctx_retour(request)
    if not request.GET.get("next"):
        retour["retour_url"] = reverse("detail_sujet", args=[sujet.id])
        retour["next_hidden"] = reverse("detail_sujet", args=[sujet.id])
    return render(
        request,
        "core/modifier_sujet.html",
        {
            "sujet": sujet,
            "filieres": filieres,
            "niveaux": niveaux,
            "annees": annees,
            **retour,
        },
    )


@email_verifie_required
def supprimer_sujet(request, sujet_id):
    if not request.user.is_staff:
        messages.error(request, "Seuls les administrateurs peuvent supprimer des sujets.")
        return redirect("bibliotheque")

    sujet = get_object_or_404(Sujet, id=sujet_id)

    if request.method == "POST" and "confirmer" in request.POST:
        titre = sujet.titre
        sujet.delete()
        messages.success(request, f"Sujet « {titre} » supprimé définitivement.")
        next_url = (request.POST.get("next") or "").strip()
        if next_url and "administration" in next_url:
            return redirect(safe_next_url(next_url, reverse("admin_sujets")))
        return redirect_apres_sujet(request)

    retour = ctx_retour(request)
    if not request.GET.get("next"):
        retour["retour_url"] = reverse("detail_sujet", args=[sujet.id])
        retour["next_hidden"] = reverse("detail_sujet", args=[sujet.id])
    return render(request, "core/supprimer_sujet.html", {"sujet": sujet, **retour})


def detail_sujet(request, sujet_id):
    try:
        sujet = (
            _sujets_accessibles(request)
            .select_related("filiere", "matiere", "niveau", "publie_par")
            .get(id=sujet_id)
        )
    except Sujet.DoesNotExist:
        messages.error(request, "Sujet introuvable.")
        return redirect(reverse("bibliotheque") + query_bibliotheque(request))

    Sujet.objects.filter(id=sujet.id).update(vues=F("vues") + 1)
    sujet.refresh_from_db(fields=["vues"])
    if request.user.is_authenticated:
        Activite.objects.create(
            utilisateur=request.user,
            type="consultation",
            sujet=sujet,
            description=f"Consultation de {sujet.titre}",
        )

    similaires = (
        _sujets_accessibles(request)
        .filter(filiere=sujet.filiere)
        .exclude(id=sujet.id)
        .select_related("filiere", "matiere")
        .order_by("-vues")[:3]
    )

    peut_modifier = request.user.is_authenticated and (
        request.user.is_staff or sujet.publie_par_id == request.user.id
    )

    biblio_retour = reverse("bibliotheque") + query_bibliotheque(request)
    return render(
        request,
        "core/detail_sujet.html",
        {
            "sujet": sujet,
            "similaires": similaires,
            "peut_modifier": peut_modifier,
            "peut_supprimer": request.user.is_staff,
            "retour_url": biblio_retour,
            "retour_label": "Retour à la bibliothèque",
            "next_detail": reverse("detail_sujet", args=[sujet.id]),
        },
    )


@login_required
@email_verifie_required
def telecharger_sujet(request, sujet_id):
    try:
        sujet = _sujets_accessibles(request).select_related("filiere", "matiere").get(id=sujet_id)
    except Sujet.DoesNotExist:
        raise Http404("Sujet introuvable")

    Sujet.objects.filter(id=sujet.id).update(telechargements=F("telechargements") + 1)
    Telechargement.objects.create(utilisateur=request.user, sujet=sujet)
    Activite.objects.create(
        utilisateur=request.user,
        type="telechargement",
        sujet=sujet,
        description=f"Téléchargement de {sujet.titre}",
    )
    return FileResponse(
        sujet.fichier_pdf.open("rb"),
        as_attachment=True,
        filename=f"{sujet.titre}.pdf",
    )


@require_POST
@login_required
def basculer_visibilite(request, sujet_id):
    """Bascule la visibilité d'un sujet (restreint ↔ visible) — admin uniquement."""
    if not request.user.is_staff:
        messages.error(request, "Action réservée aux administrateurs.")
        return redirect("bibliotheque")

    sujet = get_object_or_404(Sujet, id=sujet_id)
    if sujet.visibilite == "restreint":
        sujet.visibilite = "visible"
        msg = "Sujet désormais visible par tous."
    else:
        sujet.visibilite = "restreint"
        msg = "Sujet passé en accès restreint."
    sujet.save(update_fields=["visibilite"])
    messages.success(request, msg)
    return redirect("detail_sujet", sujet_id=sujet.id)


@login_required
def mes_sujets(request):
    """Page où l'étudiant voit ses propres soumissions et leur statut."""
    sujets = (
        Sujet.objects.filter(publie_par=request.user)
        .select_related("filiere", "matiere", "niveau")
        .order_by("-cree_le")
    )
    return render(
        request,
        "core/mes_sujets.html",
        {
            "sujets": sujets,
            **ctx_retour(request),
        },
    )
