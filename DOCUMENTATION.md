# UPGCExam — Documentation Complète

> Plateforme de partage de sujets d'examens pour l'**Université Peleforo Gon Coulibaly (UPGC)** de Korhogo, Côte d'Ivoire.
> Développé par **Tannou Abou** avec l'assistant **Nova**.

---

## 1. Présentation

UPGCExam est une application web qui permet aux étudiants de l'UPGC de **télécharger, partager et rechercher** des sujets d'examens classés par filière, matière et niveau.

### Objectifs
- Centraliser les sujets d'examens (PDF) par filière
- Permettre aux étudiants de préparer leurs examens efficacement
- Automatiser la gestion des soumissions (validation par les admins)
- Fonctionner comme une **PWA** (Progressive Web App) — installable sur téléphone

### Technologies utilisées

| Technologie | Rôle |
|---|---|
| **Python 3.12+ / Django 6.0** | Framework web back-end |
| **SQLite** | Base de données (développement — PostgreSQL en production) |
| **Tailwind CSS** | Framework CSS (interface moderne et responsive) |
| **Service Worker** | Mode hors-ligne et cache des assets statiques |
| **Web Push API (VAPID)** | Notifications push sur mobile/desktop |
| **django-allauth** | Gestion des comptes + Google OAuth (futur) |
| **python-dotenv** | Chargement automatique des variables d'environnement |
| **Git / GitHub** | Versionnement et collaboration |

---

## 2. Architecture du projet

```
upgcexam/
├── config/                    # Configuration Django
│   ├── settings.py            # Paramètres (base de données, sécurité, etc.)
│   ├── urls.py                # URLs racine
│   ├── wsgi.py / asgi.py      # Serveurs WSGI/ASGI
│   └── ...
├── core/                      # Cœur de l'application
│   ├── models.py              # Modèles de données (Sujet, Filiere, User, etc.)
│   ├── admin.py               # Interface d'administration Django
│   ├── decorators.py          # Décorateurs (email_verifie_required, staff_required)
│   ├── middleware.py          # Middleware (tracking de présence)
│   ├── navigation.py          # Utilitaires de navigation (next, retour, filtres)
│   ├── urls.py                # Routes de l'application
│   ├── utils.py               # Utilitaires (email, PDF validation)
│   ├── context_processors.py  # Variables globales pour les templates
│   ├── adapters.py            # Adaptateur Google OAuth (django-allauth)
│   ├── views/                 # Vues découpées par domaine
│   │   ├── shared.py          # Fonctions partagées (création code vérification, etc.)
│   │   ├── auth.py            # Authentification (login, inscription, vérification, reset)
│   │   ├── sujets.py          # Gestion des sujets (CRUD, recherche, téléchargement)
│   │   ├── admin.py           # Dashboard admin (stats, validation utilisateurs)
│   │   └── pwa.py             # Web Push (abonnement notifications)
│   ├── templates/core/        # Templates HTML
│   ├── static/                # Fichiers statiques (CSS, JS, PWA)
│   └── migrations/            # Migrations base de données
├── scripts/                   # Scripts utilitaires
├── manage.py                  # Point d'entrée Django
├── requirements.txt           # Dépendances Python
└── .env                       # Variables d'environnement (NON versionné)
```

### Design Pattern : MTV (Model-Template-View)
Django suit le pattern **MTV** :
- **Model** → `core/models.py` (définit les données)
- **Template** → `core/templates/` (affiche les données en HTML)
- **View** → `core/views/*.py` (logique métier)

---

## 3. Modèles de données

### Filiere
| Champ | Type | Description |
|---|---|---|
| `nom` | CharField | Nom complet (ex: "Informatique") |
| `code` | CharField (unique) | Abréviation (ex: "INFO") |
| `description` | TextField | Optionnel |
| `ordre` | PositiveIntegerField | Ordre d'affichage |

### Matiere
| Champ | Type | Description |
|---|---|---|
| `nom` | CharField | Nom de la matière |
| `filiere` | ForeignKey → Filiere | La filière associée |
| `code` | CharField | Code court |

### Niveau
| Champ | Type | Description |
|---|---|---|
| `nom` | CharField | Ex: "L1", "L2", "M1" |

### Sujet (cœur du projet)
| Champ | Type | Description |
|---|---|---|
| `titre` | CharField | Titre du sujet d'examen |
| `filiere` | ForeignKey → Filiere | Filière concernée |
| `matiere` | ForeignKey → Matiere | Matière concernée |
| `niveau` | ForeignKey → Niveau | Niveau d'étude |
| `annee_academique` | CharField | Ex: "2025-2026" |
| `fichier_pdf` | FileField | Le fichier PDF (max 10 Mo) |
| `taille_pdf` | IntegerField | Taille en octets |
| `publie_par` | ForeignKey → User | Qui a soumis |
| `statut` | CharField | `en_attente`, `actif`, `archive` |
| `vues` | PositiveIntegerField | Compteur de vues (atomique) |
| `telechargements` | PositiveIntegerField | Compteur de téléchargements (atomique) |
| `date_publication` | DateTimeField | Date de soumission |

### Utilisateur (Profil étendu)
| Champ | Type | Description |
|---|---|---|
| `user` | OneToOneField → User | Compte Django lié |
| `filiere` | ForeignKey → Filiere | Filière de l'étudiant |
| `email_verifie` | BooleanField | Email vérifié ou non |
| `date_inscription` | DateTimeField | Date d'inscription |

### Verification (codes de validation)
| Champ | Type | Description |
|---|---|---|
| `email` | EmailField | Email du demandeur |
| `code` | CharField (6) | Code à 6 chiffres |
| `expire_le` | DateTimeField | Expiration (10 min) |
| `utilise` | BooleanField | Déjà utilisé |
| `tentatives` | PositiveSmallIntegerField | Tentatives échouées (max 5) |

---

## 4. Fonctionnalités détaillées

### 4.1 Authentification

**Inscription avec vérification email :**
1. L'utilisateur remplit le formulaire d'inscription
2. Django valide le mot de passe (8 caractères min, chiffres, majuscules)
3. Un code à 6 chiffres est envoyé par email
4. L'utilisateur a 10 minutes et 5 tentatives pour le saisir
5. Après validation, l'email est marqué vérifié et l'utilisateur est connecté

**Connexion :**
- Nom d'utilisateur ou email + mot de passe
- Protection contre les redirections vers des sites externes (`safe_next_url`)

**Mot de passe oublié :**
1. Saisie de l'email
2. Envoi d'un code à 6 chiffres (valable 10 min)
3. Saisie du nouveau mot de passe
4. Validation Django intégrée

**Sécurité :**
- Codes de vérification : expiration 10 min + max 5 tentatives
- Mots de passe : validation par les règles Django
- Rate limiting : les codes sont invalidés après trop d'échecs

### 4.2 Gestion des sujets

**Soumission :**
1. L'utilisateur connecté remplit : titre, filière, matière, niveau, année, fichier PDF
2. Le PDF est validé (vrai PDF, max 10 Mo)
3. Le sujet est créé avec le statut `en_attente`
4. Un admin doit le valider avant qu'il soit visible

**Bibliothèque :**
- Affichage paginé des sujets (20 par page)
- Filtres : filière, matière, niveau, année académique
- Recherche par mot-clé
- Tri : date, popularité, matière

**Téléchargement / Vue :**
- Compteurs atomiques (`F("vues") + 1`) — pas de race condition
- Seuls les utilisateurs connectés voient les PDF
- Les admins voient les sujets en attente

### 4.3 Administration

**Dashboard admin :**
- Statistiques : nombre de sujets, utilisateurs, téléchargements
- Graphiques : sujets par filière, activités par jour
- Top contributeurs

**Gestion :**
- Validation des sujets (en_attente → actif)
- Gestion des utilisateurs (activer/bannir)
- CRUD : filières, matières, niveaux
- Consultation des codes de vérification (masqués : `XXX123`)
- Logs d'activité

### 4.4 PWA (Progressive Web App)

L'application est installable sur mobile/desktop :

- **Manifest** : icônes 192px / 512px, thème bleu (#0037B0)
- **Service Worker** :
  - Cache des assets statiques (CSS, JS, images, polices)
  - **Ne met PAS en cache** les pages privées, admin, PDFs
  - Mise à jour automatique
- **Notifications push** : abonnement via VAPID, notifications desktop

### 4.5 Sécurité

| Mesure | Détail |
|---|---|
| `DEBUG=False` en production | Pas de fuite d'infos par les erreurs |
| `SECRET_KEY` obligatoire | RuntimeError si absent et DEBUG=False |
| Rate limiting vérification | Max 5 tentatives, puis code invalidé |
| PDF validation | Vérification du format, taille max 10 Mo |
| Open redirect protection | `safe_next_url()` bloque les URLs externes |
| Staff required decorator | Centralisé, remplace les guards manuels |
| Atomic counters | `F("vues") + 1` pour éviter les race conditions |

---

## 5. Installation / Déploiement

### Prérequis
- Python 3.12+
- Git
- (Optionnel) Compte Google OAuth pour la connexion sociale

### Installation développement

```bash
# Cloner le projet
git clone https://github.com/TANNOU-dev/upgcexam.git
cd upgcexam

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Créer le fichier .env
cat > .env << EOF
DJANGO_SECRET_KEY=ta_cle_ici
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
EOF

# Migrations + démarrage
python manage.py migrate
python manage.py runserver
```

### Variables d'environnement (.env)

| Variable | Obligatoire | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Oui | Clé secrète Django |
| `DJANGO_DEBUG` | Non (defaut: false) | Mode debug |
| `DJANGO_ALLOWED_HOSTS` | Non | Hôtes autorisés (séparés par virgule) |
| `DJANGO_SECURE_SSL` | Non | Forcer HTTPS |
| `EMAIL_HOST_USER` | Non | Identifiant SMTP |
| `EMAIL_HOST_PASSWORD` | Non | Mot de passe SMTP |
| `VAPID_PUBLIC_KEY` | Non | Clé publique notifications push |
| `VAPID_PRIVATE_KEY` | Non | Clé privée notifications push |
| `VAPID_CLAIM_EMAIL` | Non | Email pour VAPID |

---

## 6. Guide utilisateur

### Étudiant
1. **Créer un compte** → inscription avec email
2. **Vérifier son email** → saisir le code reçu
3. **Parcourir les sujets** → bibliothèque avec filtres
4. **Télécharger un PDF** → cliquer sur un sujet
5. **Proposer un sujet** → formulaire d'ajout (en attente de validation)
6. **Installer l'app** → sur mobile, "Ajouter à l'écran d'accueil"

### Administrateur
1. Accéder à `/administration/` depuis le menu
2. **Dashboard** : voir les statistiques en temps réel
3. **Sujets** : valider ou refuser les soumissions
4. **Utilisateurs** : gérer les comptes
5. **Filières/Matières/Niveaux** : configurer les entités UPGC

---

## 7. API et endpoints

### URLs principales

| URL | Méthode | Description |
|---|---|---|
| `/` | GET | Page d'accueil |
| `/connexion/` | GET/POST | Connexion |
| `/inscription/` | GET/POST | Inscription |
| `/verification/` | GET/POST | Vérification email |
| `/sujets/` | GET | Bibliothèque |
| `/sujets/ajouter/` | GET/POST | Ajouter un sujet |
| `/sujets/<id>/` | GET | Détail du sujet |
| `/sujets/<id>/modifier/` | GET/POST | Modifier |
| `/sujets/<id>/supprimer/` | GET/POST | Supprimer (admin) |
| `/sujets/<id>/telecharger/` | GET | Télécharger le PDF |
| `/administration/` | GET | Dashboard admin |
| `/administration/sujets/` | GET/POST | Gestion sujets |

---

## 8. État actuel et roadmap

### ✅ Fonctionnel
- [x] Authentification complète (inscription, connexion, reset, vérification email)
- [x] Bibliothèque avec filtres et recherche
- [x] Upload de sujets avec validation PDF
- [x] Dashboard admin (stats, validation)
- [x] PWA (installable, offline assets, notifications push)
- [x] Compteurs atomiques (vues, téléchargements)
- [x] Anti-bruteforce sur les codes de vérification
- [x] Nettoyage automatique des codes expirés (commande `purge_verifications`)
- [x] Service worker intelligent (cache statique uniquement)
- [x] Gestion Centralisée des permissions admin
- [x] Chargement automatique `.env` (python-dotenv)

### 📋 À venir
- [ ] Google OAuth (connexion avec compte Google)
- [ ] Notifications push actives
- [ ] Déploiement production (PostgreSQL, Gunicorn, Nginx)
- [ ] Tests E2E automatisés avec `qa_e2e.py`
- [ ] Mode hors-ligne complet pour les sujets téléchargés
- [ ] Statistiques avancées (graphiques, heatmap)

---

## 9. Fichiers clés

| Fichier | Utilité |
|---|---|
| `config/settings.py` | Toute la configuration de l'application |
| `core/models.py` | Tous les modèles de données |
| `core/views/auth.py` | Authentification (login, register, verification, reset) |
| `core/views/sujets.py` | CRUD sujets, recherche, téléchargement |
| `core/views/admin.py` | Dashboard, stats, gestion admin |
| `core/decorators.py` | `email_verifie_required`, `staff_required` |
| `core/middleware.py` | Enregistrement du temps de présence |
| `core/utils.py` | Validation PDF, envoi d'emails, génération de codes |
| `core/navigation.py` | Navigation (next, retour, filtres) |
| `core/static/pwa/sw.js` | Service Worker (cache, notifications) |
| `scripts/update_filiere_codes.py` | Mise à jour des codes filières |
| `requirements.txt` | Dépendances Python |

---

## 10. Commandes utiles

```bash
# Lancer le serveur
python manage.py runserver 0.0.0.0:8000

# Appliquer les migrations
python manage.py migrate

# Créer une migration
python manage.py makemigrations

# Nettoyer les codes expirés
python manage.py purge_verifications

# Voir les tests disponibles
python manage.py test

# Lancer les tests E2E
python manage.py shell < core/qa_e2e.py

# Collecter les fichiers statiques
python manage.py collectstatic
```

---

*Documentation générée le 30 mai 2026 par Nova — Assistant IA de Tannou Abou.*
*Projet UPGCExam — v1.0 — https://github.com/TANNOU-dev/upgcexam*
