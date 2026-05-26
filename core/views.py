from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import ExtractWeekDay
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import email_verifie_required
from .models import (
    Activite,
    Filiere,
    Matiere,
    Niveau,
    Sujet,
    Telechargement,
    Utilisateur,
    Verification,
)
from .navigation import (
    ctx_retour,
    query_bibliotheque,
    redirect_apres_sujet,
    safe_next_url,
)
from .utils import envoyer_code_verification, est_fichier_pdf, generer_code_verification


def salutation():
    heure = timezone.now().hour
    if 6 <= heure < 12:
        return "Bonjour"
    if 12 <= heure < 18:
        return "Bon après-midi"
    if 18 <= heure < 22:
        return "Bonsoir"
    return "Bonne nuit"


def _sujets_accessibles(request):
    """Sujets actifs — les sujets 'restreint' ne sont visibles que par les administrateurs."""
    qs = Sujet.objects.filter(statut="actif").select_related("filiere", "matiere", "niveau")
    if not request.user.is_staff:
        qs = qs.filter(visibilite="visible")
    return qs


def _matieres_par_filiere():
    result = {}
    for m in Matiere.objects.select_related("filiere").order_by("nom"):
        result.setdefault(str(m.filiere_id), []).append({"id": m.id, "nom": m.nom})
    return result


def _creer_code_verification(email):
    code = generer_code_verification()
    Verification.objects.create(
        email=email,
        code=code,
        expire_le=timezone.now() + timedelta(minutes=10),
    )
    try:
        envoyer_code_verification(email, code)
    except Exception:
        if settings.DEBUG:
            messages.warning(
                None,
                "Email non envoyé (configurez SMTP). Consultez la console du serveur.",
            )
        else:
            raise
    return code


def accueil(request):
    sujets_qs = _sujets_accessibles(request)
    total_sujets = sujets_qs.count()
    total_filieres = Filiere.objects.count()
    annees_distinctes = sujets_qs.values_list("annee_academique", flat=True).distinct().count()

    sujets_populaires = []
    for sujet in sujets_qs.order_by("-vues")[:4]:
        sujets_populaires.append(
            {
                "id": sujet.id,
                "titre": sujet.titre,
                "annee": sujet.annee_academique,
                "vues": sujet.vues,
                "matiere": sujet.matiere.nom,
                "niveau": sujet.niveau.nom,
                "filiere_code": sujet.filiere.code,
            }
        )

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
        sujets = sujets.filter(filiere_id=filiere_id)
    if matiere_id:
        sujets = sujets.filter(matiere_id=matiere_id)
    if annee:
        sujets = sujets.filter(annee_academique=annee)

    paginator = Paginator(sujets, 12)
    page = request.GET.get("page", 1)
    sujets_page = paginator.get_page(page)

    filieres = Filiere.objects.all()
    matieres = Matiere.objects.select_related("filiere").all()
    annees_list = (
        _sujets_accessibles(request)
        .values_list("annee_academique", flat=True)
        .distinct()
        .order_by("-annee_academique")
    )

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


def connexion(request):
    if request.user.is_authenticated:
        return redirect("tableau_de_bord")

    if request.method == "POST":
        username_input = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username_input, password=password)
        if user:
            login(request, user)
            raw_next = request.POST.get("next") or request.GET.get("next") or ""
            return redirect(safe_next_url(raw_next))
        messages.error(request, "Nom d'utilisateur ou mot de passe incorrect")

    next_url = request.GET.get("next", "")
    return render(
        request,
        "core/login.html",
        {
            "next": next_url,
            "inscription_url": (
                f"{reverse('inscription')}?{urlencode({'next': next_url})}"
                if next_url
                else reverse("inscription")
            ),
        },
    )


def inscription(request):
    if request.user.is_authenticated:
        return redirect("tableau_de_bord")

    filieres = Filiere.objects.all()
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        filiere_id = request.POST.get("filiere", "")

        if not all([username, email, password, password2]):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
        elif password != password2:
            messages.error(request, "Les mots de passe ne correspondent pas")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà utilisé")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur est déjà pris")
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            profil = Utilisateur.objects.create(user=user)
            if filiere_id:
                try:
                    profil.filiere = Filiere.objects.get(id=filiere_id)
                    profil.save()
                except Filiere.DoesNotExist:
                    pass
            try:
                _creer_code_verification(email)
            except Exception:
                messages.error(
                    request,
                    "Compte créé mais l'envoi du code a échoué. Contactez l'administration.",
                )
                return redirect("connexion")
            request.session["email_a_verifier"] = email
            messages.info(
                request,
                "Un code de vérification a été envoyé à votre adresse email.",
            )
            return redirect("verification")

    return render(request, "core/inscription.html", {"filieres": filieres})


def verification(request):
    email = request.session.get("email_a_verifier", "")
    next_url = request.GET.get("next") or request.session.get("verification_next", "")
    if next_url:
        request.session["verification_next"] = next_url

    if request.user.is_authenticated and hasattr(request.user, "profil"):
        if request.user.is_staff or request.user.profil.email_verifie:
            request.session.pop("verification_next", None)
            return redirect(safe_next_url(next_url))

    if request.method == "POST":
        code_saisi = request.POST.get("code", "").strip()
        try:
            verif = Verification.objects.get(email=email, code=code_saisi, utilise=False)
            if verif.expire_le >= timezone.now():
                verif.utilise = True
                verif.save()
                request.session.pop("email_a_verifier", None)
                try:
                    user = User.objects.get(email=email)
                    user.backend = "django.contrib.auth.backends.ModelBackend"
                    login(request, user)
                    profil, _ = Utilisateur.objects.get_or_create(user=user)
                    profil.email_verifie = True
                    profil.save()
                except User.DoesNotExist:
                    pass
                messages.success(request, "Email vérifié avec succès.")
                request.session.pop("verification_next", None)
                return redirect(safe_next_url(next_url))
            messages.error(request, "Le code a expiré.")
        except Verification.DoesNotExist:
            messages.error(request, "Code invalide.")

    return render(
        request,
        "core/verification.html",
        {"email": email, "afficher_code_dev": settings.DEBUG},
    )


@require_POST
@login_required
def deconnexion(request):
    logout(request)
    return redirect("accueil")


@login_required
def parametres(request):
    if request.method == "POST":
        user = request.user
        nouveau_username = request.POST.get("username", "").strip()
        nouvel_email = request.POST.get("email", "").strip()
        ancien_mdp = request.POST.get("ancien_mot_de_passe", "")
        nouveau_mdp = request.POST.get("nouveau_mot_de_passe", "")

        changer_mdp = bool(nouveau_mdp)
        changer_profil = bool(
            (nouveau_username and nouveau_username != user.username)
            or (nouvel_email and nouvel_email != user.email)
        )

        if not changer_mdp and not changer_profil:
            messages.warning(request, "Aucune modification détectée.")
            return redirect("parametres")

        if changer_mdp:
            if not ancien_mdp or not user.check_password(ancien_mdp):
                messages.error(request, "Ancien mot de passe incorrect")
                return redirect("parametres")

        if nouveau_username and nouveau_username != user.username:
            if User.objects.filter(username=nouveau_username).exclude(id=user.id).exists():
                messages.error(request, "Ce nom d'utilisateur est déjà pris")
                return redirect("parametres")
            user.username = nouveau_username

        if nouvel_email and nouvel_email != user.email:
            if User.objects.filter(email=nouvel_email).exclude(id=user.id).exists():
                messages.error(request, "Cet email est déjà utilisé")
                return redirect("parametres")
            user.email = nouvel_email

        if nouveau_mdp:
            user.set_password(nouveau_mdp)
            update_session_auth_hash(request, user)

        user.save()
        messages.success(request, "Informations mises à jour avec succès !")
        return redirect("parametres")

    return render(request, "core/parametres.html")


@email_verifie_required
def recherche(request):
    query = request.GET.get("q", "").strip()
    filieres = Filiere.objects.all()
    sujets_base = _sujets_accessibles(request)
    annees = (
        sujets_base.values_list("annee_academique", flat=True).distinct().order_by("-annee_academique")
    )

    resultats = sujets_base.none()
    if query:
        resultats = sujets_base.filter(
            Q(titre__icontains=query)
            | Q(description__icontains=query)
            | Q(auteur_nom__icontains=query)
            | Q(matiere__nom__icontains=query)
        ).order_by("-vues")

    suggestions = sujets_base.order_by("-vues")[:4]
    docs_populaires = sujets_base.order_by("-vues")[:2]

    return render(
        request,
        "core/recherche.html",
        {
            "query": query,
            "resultats": resultats,
            "total_resultats": resultats.count(),
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
    annees = (
        Sujet.objects.filter(statut="actif")
        .values_list("annee_academique", flat=True)
        .distinct()
        .order_by("-annee_academique")
    )

    if request.method == "POST":
        titre = request.POST.get("titre", "").strip()
        filiere_id = request.POST.get("filiere")
        matiere_id = request.POST.get("matiere")
        niveau_id = request.POST.get("niveau")
        annee_academique = request.POST.get("annee_academique", "").strip()
        fichier = request.FILES.get("fichier_pdf")

        if not all([titre, filiere_id, matiere_id, niveau_id, annee_academique, fichier]):
            messages.error(request, "Tous les champs sont obligatoires.")
        elif not est_fichier_pdf(fichier):
            messages.error(request, "Seuls les fichiers PDF valides sont acceptés.")
        elif not Matiere.objects.filter(id=matiere_id, filiere_id=filiere_id).exists():
            messages.error(request, "La matière sélectionnée ne correspond pas à la filière.")
        else:
            sujet = Sujet.objects.create(
                titre=titre,
                filiere_id=filiere_id,
                matiere_id=matiere_id,
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
            return redirect_apres_sujet(request)

    return render(
        request,
        "core/ajouter_sujet.html",
        {
            "filieres": filieres,
            "niveaux": niveaux,
            "annees": annees,
            "matieres_par_filiere": _matieres_par_filiere(),
            **ctx_retour(request),
        },
    )


def _get_sujet_modifiable(request, sujet_id):
    """Retourne le sujet modifiable — les admins peuvent tout modifier,
    les etudiants ne peuvent modifier que leurs propres sujets (actifs ou archivés)."""
    if request.user.is_staff:
        return get_object_or_404(Sujet, id=sujet_id)
    return get_object_or_404(
        Sujet,
        id=sujet_id,
        publie_par=request.user,
    )


@email_verifie_required
def modifier_sujet(request, sujet_id):
    sujet = _get_sujet_modifiable(request, sujet_id)

    filieres = Filiere.objects.all()
    matieres = Matiere.objects.all()
    niveaux = Niveau.objects.all()
    annees = (
        Sujet.objects.filter(statut="actif")
        .values_list("annee_academique", flat=True)
        .distinct()
        .order_by("-annee_academique")
    )

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
        matiere_id = request.POST.get("matiere")
        niveau_id = request.POST.get("niveau")
        annee_academique = request.POST.get("annee_academique", "").strip()
        description = request.POST.get("description", "")
        fichier = request.FILES.get("fichier_pdf")
        visibilite = request.POST.get("visibilite", "visible")

        if titre:
            sujet.titre = titre
        if filiere_id:
            sujet.filiere_id = filiere_id
        if matiere_id:
            sujet.matiere_id = matiere_id
        if niveau_id:
            sujet.niveau_id = niveau_id
        if annee_academique:
            sujet.annee_academique = annee_academique
        sujet.description = description
        if fichier:
            if not est_fichier_pdf(fichier):
                messages.error(request, "Seuls les fichiers PDF valides sont acceptés.")
                return redirect("modifier_sujet", sujet_id=sujet.id)
            sujet.fichier_pdf = fichier

        # Seuls les admins peuvent changer la visibilite
        # Les modifs d'un non-admin replacent le sujet en attente de validation
        if request.user.is_staff:
            sujet.visibilite = visibilite
            sujet.save()
            messages.success(request, "Sujet modifié avec succès.")
            return redirect_apres_sujet(request, sujet=sujet, defaut="detail_sujet")
        else:
            sujet.statut = "archive"
            sujet.save()
            messages.success(request, "✅ Modifications enregistrées. En attente.")
            # Rediriger vers la bibliotheque (le sujet n'est plus visible)
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
            "matieres": matieres,
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

    sujet.vues += 1
    sujet.save(update_fields=["vues"])
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

    sujet.telechargements += 1
    sujet.save(update_fields=["telechargements"])
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


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("tableau_de_bord")

    stats = {
        "total_sujets": Sujet.objects.count(),
        "sujets_actifs": Sujet.objects.filter(statut="actif").count(),
        "sujets_en_attente": Sujet.objects.filter(statut="en_attente").count(),
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
    for i, filiere in enumerate(Filiere.objects.all()[:5]):
        total_sujets = Sujet.objects.filter(filiere=filiere, statut="actif").count()
        if total_sujets > 0:
            vus = (
                Activite.objects.filter(
                    utilisateur_id=user_id, sujet__filiere=filiere, type="consultation"
                )
                .values("sujet")
                .distinct()
                .count()
            )
            pct = min(int(vus * 100 / total_sujets), 100)
        else:
            pct = 0
        progressions.append(
            {"nom": filiere.nom, "pourcentage": pct, "couleur": couleurs[i % len(couleurs)]}
        )

    jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    activite_hebdo = Activite.objects.filter(utilisateur_id=user_id)
    if activite_hebdo.exists():
        jours_act = (
            activite_hebdo.annotate(jour_sem=ExtractWeekDay("cree_le"))
            .values("jour_sem")
            .annotate(count=Count("id"))
        )
        mapping = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
        valeurs = [0] * 7
        for j in jours_act:
            valeurs[mapping[j["jour_sem"]]] = min(j["count"] * 10, 100)
        activite = list(zip(jours, valeurs))
    else:
        activite = list(zip(jours, [0] * 7))

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
        Filiere.objects.annotate(nb_sujets=Count("sujets"), nb_etudiants=Count("etudiants")).order_by(
            "code"
        )
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

    activites = Activite.objects.select_related("utilisateur", "sujet").order_by("-cree_le")[:100]
    telechargements = (
        Telechargement.objects.select_related("utilisateur", "sujet").order_by("-telecharge_le")[:100]
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

        if action == "valider" and sujet_id:
            updated = Sujet.objects.filter(id=sujet_id, statut="en_attente").update(statut="actif")
            if updated:
                messages.success(request, "Sujet validé et publié.")
            else:
                messages.error(request, "Sujet introuvable ou déjà traité.")
        elif action == "archiver" and sujet_id:
            Sujet.objects.filter(id=sujet_id, statut="actif").update(statut="archive")
            messages.success(request, "Sujet archivé.")
        elif action == "reactiver" and sujet_id:
            Sujet.objects.filter(id=sujet_id, statut="archive").update(statut="actif")
            messages.success(request, "Sujet réactivé et visible par tous.")
        elif action == "supprimer" and sujet_id:
        
            Sujet.objects.filter(id=sujet_id).delete()
            messages.success(request, "Sujet supprimé définitivement.")
        return redirect("admin_sujets")

    filtre_statut = request.GET.get("statut", "")
    filtre_filiere = request.GET.get("filiere", "")
    filtre_annee = request.GET.get("annee", "")

    sujets = Sujet.objects.select_related("filiere", "matiere", "niveau", "publie_par").order_by(
        "-cree_le"
    )
    if filtre_statut:
        sujets = sujets.filter(statut=filtre_statut)
    if filtre_filiere:
        sujets = sujets.filter(filiere_id=filtre_filiere)
    if filtre_annee:
        sujets = sujets.filter(annee_academique=filtre_annee)

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
            "stats": {
                "total": Sujet.objects.count(),
                "actifs": Sujet.objects.filter(statut="actif").count(),
                "en_attente": Sujet.objects.filter(statut="en_attente").count(),
                "archives": Sujet.objects.filter(statut="archive").count(),
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
                    _creer_code_verification(email)
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

    codes = Verification.objects.filter(utilise=False, expire_le__gte=timezone.now()).order_by(
        "-expire_le"
    )
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
