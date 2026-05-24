from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import ExtractWeekDay
from django.db.models import Count
from .models import Verification, Activite, Telechargement, Matiere, Filiere, Sujet, Utilisateur, Niveau
from django.utils import timezone
from datetime import timedelta
import random


def salutation():
    heure = timezone.now().hour
    if 6 <= heure < 12:
        return "Bonjour"
    elif 12 <= heure < 18:
        return "Bon après-midi"
    elif 18 <= heure < 22:
        return "Bonsoir"
    else:
        return "Bonne nuit"


def accueil(request):
    total_sujets = Sujet.objects.filter(statut='actif').count()
    total_filieres = Filiere.objects.count()
    annees = Sujet.objects.filter(statut='actif').values_list('annee_academique', flat=True).distinct()
    annees_distinctes = len(annees)

    sujets_populaires = []
    for sujet in Sujet.objects.filter(statut='actif').order_by('-vues')[:4]:
        sujets_populaires.append({
            'titre': sujet.titre,
            'annee': sujet.annee_academique,
            'vues': sujet.vues,
            'matiere': sujet.matiere.nom,
            'niveau': sujet.niveau.nom,
            'filiere_code': sujet.filiere.code,
        })

    return render(request, 'core/accueil.html', {
        'total_sujets': total_sujets,
        'total_filieres': total_filieres,
        'annees_distinctes': annees_distinctes,
        'sujets_populaires': sujets_populaires,
    })


def bibliotheque(request):
    query = request.GET.get('q', '')
    filiere_id = request.GET.get('filiere', '')
    matiere_id = request.GET.get('matiere', '')
    annee = request.GET.get('annee', '')

    sujets = Sujet.objects.filter(statut='actif').select_related('filiere', 'matiere', 'niveau').order_by('-date_publication')

    if query:
        sujets = sujets.filter(titre__icontains=query) | sujets.filter(description__icontains=query)
    if filiere_id:
        sujets = sujets.filter(filiere_id=filiere_id)
    if matiere_id:
        sujets = sujets.filter(matiere_id=matiere_id)
    if annee:
        sujets = sujets.filter(annee_academique=annee)

    paginator = Paginator(sujets, 12)
    page = request.GET.get('page', 1)
    sujets_page = paginator.get_page(page)

    filieres = Filiere.objects.all()
    matieres = Matiere.objects.all()
    annees_list = Sujet.objects.filter(statut='actif').values_list('annee_academique', flat=True).distinct().order_by('-annee_academique')

    return render(request, 'core/bibliotheque.html', {
        'sujets': sujets_page,
        'filieres': filieres,
        'matieres': matieres,
        'annees': annees_list,
        'query': query,
        'filiere_id': filiere_id,
        'matiere_id': matiere_id,
        'annee': annee,
    })


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 — Open Redirect : valider que next_url est un chemin interne
# ─────────────────────────────────────────────────────────────────────────────
def _safe_next_url(next_url, fallback='tableau_de_bord'):
    """
    Retourne next_url uniquement s'il s'agit d'un chemin relatif interne
    (commence par '/') afin d'empêcher les redirections vers des sites externes.
    Sinon retourne le nom de vue fallback.
    """
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return fallback


def connexion(request):
    if request.method == 'POST':
        username_input = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username_input, password=password)
        if user:
            login(request, user)
            raw_next = request.POST.get('next') or request.GET.get('next') or ''
            next_url = _safe_next_url(raw_next)
            if not next_url.startswith('/'):
                return redirect(next_url)
            return redirect(next_url)
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect")
    next_url = request.GET.get('next', '')
    return render(request, 'core/login.html', {'next': next_url})


def inscription(request):
    filieres = Filiere.objects.all()
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        password2 = request.POST['password2']
        filiere_id = request.POST.get('filiere', '')
        if password != password2:
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
            code = str(random.randint(100000, 999999))
            Verification.objects.create(
                email=email, code=code,
                expire_le=timezone.now() + timedelta(minutes=10)
            )
            request.session['email_a_verifier'] = email
            return redirect(f'/verification/?code={code}')
    return render(request, 'core/inscription.html', {'filieres': filieres})


def verification(request):
    email = request.session.get('email_a_verifier', '')
    code_envoye = request.GET.get('code', '')
    if request.method == 'POST':
        code_saisi = request.POST.get('code', '')
        try:
            verif = Verification.objects.get(email=email, code=code_saisi, utilise=False)
            if verif.expire_le >= timezone.now():
                verif.utilise = True
                verif.save()
                request.session.pop('email_a_verifier', None)
                try:
                    user = User.objects.get(email=email)
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                    login(request, user)
                    profil, created = Utilisateur.objects.get_or_create(user=user)
                    profil.email_verifie = True
                    profil.save()
                except User.DoesNotExist:
                    pass
                return redirect('tableau_de_bord')
            else:
                messages.error(request, "Le code a expiré.")
        except Verification.DoesNotExist:
            messages.error(request, "Code invalide.")
    return render(request, 'core/verification.html', {'email': email, 'code_envoye': code_envoye})


@login_required
def deconnexion(request):
    logout(request)
    return redirect('accueil')


@login_required
def parametres(request):
    if request.method == 'POST':
        user = request.user
        nouveau_username = request.POST.get('username')
        nouvel_email = request.POST.get('email')
        ancien_mdp = request.POST.get('ancien_mot_de_passe', '')
        nouveau_mdp = request.POST.get('nouveau_mot_de_passe', '')

        if not user.check_password(ancien_mdp):
            messages.error(request, "Ancien mot de passe incorrect")
        else:
            if nouveau_username and nouveau_username != user.username:
                if User.objects.filter(username=nouveau_username).exclude(id=user.id).exists():
                    messages.error(request, "Ce nom d'utilisateur est déjà pris")
                else:
                    user.username = nouveau_username
            if nouvel_email and nouvel_email != user.email:
                if User.objects.filter(email=nouvel_email).exclude(id=user.id).exists():
                    messages.error(request, "Cet email est déjà utilisé")
                else:
                    user.email = nouvel_email
            if nouveau_mdp:
                user.set_password(nouveau_mdp)
            user.save()
            messages.success(request, "Informations mises à jour avec succès !")
            from django.contrib.auth import update_session_auth_hash
            if nouveau_mdp:
                update_session_auth_hash(request, user)
            return redirect('parametres')
    return render(request, 'core/parametres.html')


@login_required
def recherche(request):
    query = request.GET.get('q', '')
    filieres = Filiere.objects.all()
    annees = Sujet.objects.filter(statut='actif').values_list('annee_academique', flat=True).distinct().order_by('-annee_academique')

    resultats = Sujet.objects.none()
    if query:
        resultats = Sujet.objects.filter(
            Q(statut='actif'),
            Q(titre__icontains=query) | Q(description__icontains=query) | Q(auteur_nom__icontains=query) | Q(matiere__nom__icontains=query)
        ).select_related('filiere', 'matiere', 'niveau').order_by('-vues')

    suggestions = Sujet.objects.filter(statut='actif').select_related('filiere', 'matiere', 'niveau').order_by('-vues')[:4]
    docs_populaires = Sujet.objects.filter(statut='actif').select_related('filiere', 'matiere', 'niveau').order_by('-vues')[:2]

    return render(request, 'core/recherche.html', {
        'query': query,
        'resultats': resultats,
        'total_resultats': resultats.count(),
        'filieres': filieres,
        'annees': annees,
        'suggestions': suggestions,
        'docs_populaires': docs_populaires,
    })


@login_required
def ajouter_sujet(request):
    filieres = Filiere.objects.all()
    matieres = Matiere.objects.all()
    niveaux = Niveau.objects.all()
    annees = Sujet.objects.filter(statut='actif').values_list('annee_academique', flat=True).distinct().order_by('-annee_academique')

    if request.method == 'POST':
        titre = request.POST.get('titre')
        filiere_id = request.POST.get('filiere')
        matiere_id = request.POST.get('matiere')
        niveau_id = request.POST.get('niveau')
        annee_academique = request.POST.get('annee_academique')
        fichier = request.FILES.get('fichier_pdf')

        if not all([titre, filiere_id, matiere_id, niveau_id, annee_academique, fichier]):
            messages.error(request, 'Tous les champs sont obligatoires.')
        elif fichier.content_type != 'application/pdf':
            messages.error(request, 'Seuls les fichiers PDF sont acceptés.')
        else:
            Sujet.objects.create(
                titre=titre,
                filiere_id=filiere_id,
                matiere_id=matiere_id,
                niveau_id=niveau_id,
                annee_academique=annee_academique,
                fichier_pdf=fichier,
                publie_par=request.user,
                statut='archive',
                visibilite='visible',
            )
            Activite.objects.create(
                utilisateur=request.user,
                type='consultation',
                description=f"Ajout du sujet : {titre}",
            )
            messages.success(request, 'Sujet ajouté avec succès ! En attente de validation.')
            return redirect('bibliotheque')

    return render(request, 'core/ajouter_sujet.html', {
        'filieres': filieres,
        'matieres': matieres,
        'niveaux': niveaux,
        'annees': annees,
    })


# ─────────────────────────────────────────────────────────────────────────────
# FIX 2 — modifier_sujet : vérifier propriété ou staff
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def modifier_sujet(request, sujet_id):
    try:
        sujet = Sujet.objects.get(id=sujet_id, statut='actif')
    except Sujet.DoesNotExist:
        messages.error(request, 'Sujet introuvable.')
        return redirect('bibliotheque')

    if sujet.publie_par != request.user and not request.user.is_staff:
        messages.error(request, "Vous n'avez pas la permission de modifier ce sujet.")
        return redirect('bibliotheque')

    filieres = Filiere.objects.all()
    annees = Sujet.objects.filter(statut='actif').values_list('annee_academique', flat=True).distinct().order_by('-annee_academique')

    if request.method == 'POST':
        if 'archiver' in request.POST:
            sujet.statut = 'archive'
            sujet.save()
            messages.success(request, 'Sujet archivé avec succès.')
            return redirect('bibliotheque')

        titre = request.POST.get('titre')
        filiere_id = request.POST.get('filiere')
        annee_academique = request.POST.get('annee_academique')
        description = request.POST.get('description', '')
        fichier = request.FILES.get('fichier_pdf')
        visibilite = request.POST.get('visibilite', 'visible')

        if titre:
            sujet.titre = titre
        if filiere_id:
            sujet.filiere_id = filiere_id
        if annee_academique:
            sujet.annee_academique = annee_academique
        sujet.description = description
        sujet.visibilite = visibilite
        if fichier:
            sujet.fichier_pdf = fichier
        sujet.save()

        messages.success(request, 'Sujet mis à jour avec succès.')
        return redirect('bibliotheque')

    return render(request, 'core/modifier_sujet.html', {
        'sujet': sujet,
        'filieres': filieres,
        'annees': annees,
    })


# ─────────────────────────────────────────────────────────────────────────────
# FIX 3 — supprimer_sujet : vérifier propriété ou staff + filtre statut
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def supprimer_sujet(request, sujet_id):
    try:
        sujet = Sujet.objects.get(id=sujet_id, statut='actif')
    except Sujet.DoesNotExist:
        messages.error(request, 'Sujet introuvable.')
        return redirect('bibliotheque')

    # Seul un admin (staff) peut supprimer un sujet
    if not request.user.is_staff:
        messages.error(request, "Seuls les administrateurs peuvent supprimer des sujets.")
        return redirect('bibliotheque')

    if request.method == 'POST' and 'confirmer' in request.POST:
        titre = sujet.titre
        sujet.delete()
        messages.success(request, f"Sujet « {titre} » supprimé définitivement.")
        return redirect('bibliotheque')

    return render(request, 'core/supprimer_sujet.html', {
        'sujet': sujet,
    })


@login_required
def telecharger_sujet(request, sujet_id):
    from django.http import FileResponse, Http404
    try:
        sujet = Sujet.objects.select_related('filiere', 'matiere').get(id=sujet_id, statut='actif')
    except Sujet.DoesNotExist:
        raise Http404('Sujet introuvable')

    sujet.telechargements += 1
    sujet.save(update_fields=['telechargements'])

    Telechargement.objects.create(utilisateur=request.user, sujet=sujet)

    Activite.objects.create(
        utilisateur=request.user,
        type='telechargement',
        sujet=sujet,
        description=f"Téléchargement de {sujet.titre}"
    )

    return FileResponse(sujet.fichier_pdf.open('rb'), as_attachment=True, filename=f"{sujet.titre}.pdf")


@login_required
def detail_sujet(request, sujet_id):
    try:
        sujet = Sujet.objects.select_related('filiere', 'matiere', 'niveau', 'publie_par').get(id=sujet_id, statut='actif')
    except Sujet.DoesNotExist:
        messages.error(request, 'Sujet introuvable.')
        return redirect('bibliotheque')

    sujet.vues += 1
    sujet.save(update_fields=['vues'])

    Activite.objects.create(utilisateur=request.user, type='consultation', sujet=sujet, description=f"Consultation de {sujet.titre}")

    similaires = Sujet.objects.filter(statut='actif', filiere=sujet.filiere).exclude(id=sujet.id).select_related('filiere', 'matiere').order_by('-vues')[:3]

    return render(request, 'core/detail_sujet.html', {
        'sujet': sujet,
        'similaires': similaires,
    })


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('tableau_de_bord')

    stats = {
        'total_sujets': Sujet.objects.count(),
        'sujets_actifs': Sujet.objects.filter(statut='actif').count(),
        'sujets_en_attente': Sujet.objects.filter(statut='archive').count(),
        'total_utilisateurs': User.objects.count(),
        'total_telechargements': Telechargement.objects.count(),
    }

    sujets_recents = Sujet.objects.select_related('filiere', 'publie_par').order_by('-cree_le')[:10]
    utilisateurs_recents = User.objects.select_related('profil').order_by('-date_joined')[:10]
    sujets_en_attente = Sujet.objects.filter(statut='archive').select_related('filiere', 'matiere', 'niveau', 'publie_par').order_by('-cree_le')[:10]

    if request.method == 'POST' and 'valider_sujet' in request.POST:
        sujet_id = request.POST.get('sujet_id')
        try:
            sujet = Sujet.objects.get(id=sujet_id, statut='archive')
            sujet.statut = 'actif'
            sujet.save()
            messages.success(request, f"Sujet « {sujet.titre} » validé et publié.")
        except Sujet.DoesNotExist:
            messages.error(request, 'Sujet introuvable.')
        return redirect('admin_dashboard')

    return render(request, 'core/admin_dashboard.html', {
        'stats': stats,
        'sujets_recents': sujets_recents,
        'utilisateurs_recents': utilisateurs_recents,
        'sujets_en_attente': sujets_en_attente,
    })


@login_required
def tableau_de_bord(request):
    user_id = request.user.id
    sujets_vus = Activite.objects.filter(utilisateur_id=user_id, type='consultation').count()
    pdfs_telecharges = Telechargement.objects.filter(utilisateur_id=user_id).count()
    total_matieres = Matiere.objects.count()
    total_filieres = Filiere.objects.count()
    stats = {
        'sujets_vus': sujets_vus,
        'pdfs_telecharges': pdfs_telecharges,
        'matieres': total_matieres,
        'filieres': total_filieres,
    }
    progressions = []
    couleurs = ['#0037B0', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6']
    for i, filiere in enumerate(Filiere.objects.all()[:5]):
        total_sujets = Sujet.objects.filter(filiere=filiere).count()
        if total_sujets > 0:
            vus = Activite.objects.filter(utilisateur_id=user_id, sujet__filiere=filiere).values('sujet').distinct().count()
            pct = min(int(vus * 100 / total_sujets), 100)
        else:
            pct = 0
        progressions.append({'nom': filiere.nom, 'pourcentage': pct, 'couleur': couleurs[i % len(couleurs)]})

    jours = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    activite_hebdo = Activite.objects.filter(utilisateur_id=user_id)
    if activite_hebdo.exists():
        jours_act = activite_hebdo.annotate(jour_sem=ExtractWeekDay('cree_le')).values('jour_sem').annotate(count=Count('id'))
        mapping = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
        valeurs = [0] * 7
        for j in jours_act:
            valeurs[mapping[j['jour_sem']]] = min(j['count'] * 10, 100)
        activite = list(zip(jours, valeurs))
    else:
        activite = list(zip(jours, [0] * 7))

    sujets_recommandes = []
    for sujet in Sujet.objects.filter(statut='actif').order_by('-vues')[:3]:
        sujets_recommandes.append({'titre': sujet.titre, 'annee': sujet.annee_academique})

    activites_recentes = []
    for act in Activite.objects.filter(utilisateur_id=user_id).order_by('-cree_le')[:5]:
        depuis = timezone.now() - act.cree_le
        if depuis.total_seconds() < 60:
            temps = "Il y a quelques secondes"
        elif depuis.total_seconds() < 3600:
            temps = f"Il y a {int(depuis.total_seconds() // 60)} minutes"
        elif depuis.total_seconds() < 86400:
            temps = f"Il y a {int(depuis.total_seconds() // 3600)} heures"
        else:
            temps = f"Il y a {int(depuis.total_seconds() // 86400)} jours"
        activites_recentes.append({
            'type': act.type,
            'description': act.description or f"{dict(Activite.TYPE_CHOICES).get(act.type, act.type)} de sujet",
            'temps': temps,
        })

    return render(request, 'core/tableau_de_bord.html', {
        'stats': stats, 'progressions': progressions,
        'activite': activite, 'sujets_recommandes': sujets_recommandes,
        'activites_recentes': activites_recentes,
        'salutation': salutation(),
    })


# ====================================================================
# VUES ADMIN PERSONNALISÉES
# ====================================================================


@login_required
def admin_utilisateurs(request):
    """Liste et gestion des utilisateurs."""
    if not request.user.is_staff:
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('tableau_de_bord')

    # Actions POST
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')

        if action == 'toggle_staff' and user_id:
            target = User.objects.get(id=user_id)
            if target != request.user:  # Empêcher de se désactiver soi-même
                target.is_staff = not target.is_staff
                target.save()
                messages.success(request, f"Rôle de {target.username} mis à jour.")
            else:
                messages.error(request, "Vous ne pouvez pas modifier votre propre rôle.")

        elif action == 'toggle_active' and user_id:
            target = User.objects.get(id=user_id)
            if target != request.user:
                target.is_active = not target.is_active
                target.save()
                status = 'activé' if target.is_active else 'désactivé'
                messages.success(request, f"Compte de {target.username} {status}.")
            else:
                messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")

        elif action == 'delete_user' and user_id:
            target = User.objects.get(id=user_id)
            if target != request.user and not target.is_superuser:
                target.delete()
                messages.success(request, f"Utilisateur {target.username} supprimé.")
            else:
                messages.error(request, "Impossible de supprimer cet utilisateur.")

        return redirect('admin_utilisateurs')

    utilisateurs = User.objects.select_related('profil').order_by('-date_joined')

    # Stats
    total = utilisateurs.count()
    actifs = utilisateurs.filter(is_active=True).count()
    staff = utilisateurs.filter(is_staff=True).count()

    return render(request, 'core/admin/utilisateurs.html', {
        'utilisateurs': utilisateurs,
        'total': total,
        'actifs': actifs,
        'staff': staff,
    })


@login_required
def admin_filieres(request):
    """Gestion CRUD des filières."""
    if not request.user.is_staff:
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('tableau_de_bord')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ajouter':
            nom = request.POST.get('nom', '').strip()
            code = request.POST.get('code', '').strip().upper()
            if nom and code:
                Filiere.objects.create(nom=nom, code=code)
                messages.success(request, f'Filière {code} - {nom} ajoutée.')
            else:
                messages.error(request, 'Nom et code requis.')

        elif action == 'modifier':
            fid = request.POST.get('filiere_id')
            nom = request.POST.get('nom', '').strip()
            code = request.POST.get('code', '').strip().upper()
            if fid and nom and code:
                Filiere.objects.filter(id=fid).update(nom=nom, code=code)
                messages.success(request, 'Filière modifiée.')

        elif action == 'supprimer':
            fid = request.POST.get('filiere_id')
            if fid:
                Filiere.objects.filter(id=fid).delete()
                messages.success(request, 'Filière supprimée.')

        return redirect('admin_filieres')

    filieres = Filiere.objects.annotate(nb_sujets=Count('sujets'), nb_etudiants=Count('etudiants')).order_by('code')
    return render(request, 'core/admin/filieres.html', {'filieres': filieres})


@login_required
def admin_matieres(request):
    """Gestion CRUD des matières."""
    if not request.user.is_staff:
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('tableau_de_bord')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ajouter':
            nom = request.POST.get('nom', '').strip()
            filiere_id = request.POST.get('filiere_id')
            if nom and filiere_id:
                Matiere.objects.create(nom=nom, filiere_id=filiere_id)
                messages.success(request, f'Matière {nom} ajoutée.')
            else:
                messages.error(request, 'Nom et filière requis.')

        elif action == 'supprimer':
            mid = request.POST.get('matiere_id')
            if mid:
                Matiere.objects.filter(id=mid).delete()
                messages.success(request, 'Matière supprimée.')

        return redirect('admin_matieres')

    matieres = Matiere.objects.select_related('filiere').annotate(nb_sujets=Count('sujets')).order_by('filiere__code', 'nom')
    filieres = Filiere.objects.all()
    return render(request, 'core/admin/matieres.html', {'matieres': matieres, 'filieres': filieres})


@login_required
def admin_niveaux(request):
    """Gestion CRUD des niveaux."""
    if not request.user.is_staff:
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('tableau_de_bord')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ajouter':
            nom = request.POST.get('nom', '').strip()
            if nom:
                Niveau.objects.create(nom=nom)
                messages.success(request, f'Niveau {nom} ajouté.')

        elif action == 'supprimer':
            nid = request.POST.get('niveau_id')
            if nid:
                Niveau.objects.filter(id=nid).delete()
                messages.success(request, 'Niveau supprimé.')

        return redirect('admin_niveaux')

    niveaux = Niveau.objects.annotate(nb_sujets=Count('sujets')).order_by('nom')
    return render(request, 'core/admin/niveaux.html', {'niveaux': niveaux})


@login_required
def admin_logs(request):
    """Logs d'activité et téléchargements."""
    if not request.user.is_staff:
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('tableau_de_bord')

    activites = Activite.objects.select_related('utilisateur', 'sujet').order_by('-cree_le')[:100]
    telechargements = Telechargement.objects.select_related('utilisateur', 'sujet').order_by('-telecharge_le')[:100]

    return render(request, 'core/admin/logs.html', {
        'activites': activites,
        'telechargements': telechargements,
    })


@login_required
def admin_sujets(request):
    """Gestion complète des sujets dans l'admin."""
    if not request.user.is_staff:
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('tableau_de_bord')

    from django.http import FileResponse, Http404

    # Actions POST
    if request.method == 'POST':
        action = request.POST.get('action')
        sujet_id = request.POST.get('sujet_id')

        if action == 'valider' and sujet_id:
            Sujet.objects.filter(id=sujet_id, statut='archive').update(statut='actif')
            messages.success(request, 'Sujet validé et publié.')

        elif action == 'archiver' and sujet_id:
            Sujet.objects.filter(id=sujet_id, statut='actif').update(statut='archive')
            messages.success(request, 'Sujet archivé.')

        elif action == 'supprimer' and sujet_id:
            Sujet.objects.filter(id=sujet_id).delete()
            messages.success(request, 'Sujet supprimé définitivement.')

        return redirect('admin_sujets')

    # Filtres
    filtre_statut = request.GET.get('statut', '')
    filtre_filiere = request.GET.get('filiere', '')
    filtre_annee = request.GET.get('annee', '')

    sujets = Sujet.objects.select_related('filiere', 'matiere', 'niveau', 'publie_par').order_by('-cree_le')

    if filtre_statut:
        sujets = sujets.filter(statut=filtre_statut)
    if filtre_filiere:
        sujets = sujets.filter(filiere_id=filtre_filiere)
    if filtre_annee:
        sujets = sujets.filter(annee_academique=filtre_annee)

    paginator = Paginator(sujets, 25)
    page = request.GET.get('page', 1)
    sujets_page = paginator.get_page(page)

    filieres = Filiere.objects.all()
    annees = Sujet.objects.values_list('annee_academique', flat=True).distinct().order_by('-annee_academique')

    stats = {
        'total': Sujet.objects.count(),
        'actifs': Sujet.objects.filter(statut='actif').count(),
        'archives': Sujet.objects.filter(statut='archive').count(),
    }

    return render(request, 'core/admin/sujets.html', {
        'sujets': sujets_page,
        'filieres': filieres,
        'annees': annees,
        'filtre_statut': filtre_statut,
        'filtre_filiere': filtre_filiere,
        'filtre_annee': filtre_annee,
        'stats': stats,
    })


@login_required
def admin_voir_sujet_pdf(request, sujet_id):
    """Permet à l'admin de visualiser le PDF d'un sujet (même archivé)."""
    if not request.user.is_staff:
        raise Http404()

    from django.http import FileResponse
    try:
        sujet = Sujet.objects.get(id=sujet_id)
    except Sujet.DoesNotExist:
        raise Http404('Sujet introuvable')

    return FileResponse(sujet.fichier_pdf.open('rb'), filename=f"{sujet.titre}.pdf")
