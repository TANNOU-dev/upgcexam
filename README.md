# 🎓 UPGCExam

**Plateforme d'archivage et de consultation des sujets d'examens de l'Université Péléforo Gon Coulibaly (UPGC) — Korhogo, Côte d'Ivoire.**

> L'excellence académique, numérisée.

---

## 📋 Table des matières

- [Contexte & Vision](#contexte--vision)
- [Stack Technique](#stack-technique)
- [Structure du Projet](#structure-du-projet)
- [Ce qui a été fait](#ce-qui-a-été-fait)
- [Roadmap](#roadmap)
- [Installation](#installation)
- [Équipe](#équipe)

---

## Contexte & Vision

### Problème
Les étudiants de l'UPGC n'ont pas d'accès centralisé et structuré aux annales d'examens des années précédentes. Les sujets sont dispersés (papier, fichiers personnels, WhatsApp…) et difficiles à trouver.

### Solution
**UPGCExam** — une plateforme web qui permet :
- 📖 **Consulter** les sujets d'examens par filière, matière, niveau et année
- 🔍 **Rechercher** des sujets avec filtres avancés
- 📥 **Télécharger** les annales en PDF
- 👨‍🎓 **S'inscrire** et suivre sa progression personnelle
- 🛡️ **Administration** pour valider et gérer les contenus

### Vision long-terme
Devenir la bibliothèque numérique de référence de l'UPGC, avec :
- ✅ Plus de 500 annales référencées
- ✅ Certification officielle UPGC
- ✅ Suivi personnalisé de progression
- ✅ Contribution collaborative (étudiants + enseignants)

---

## Stack Technique

| Composant       | Technologie               |
|-----------------|---------------------------|
| **Backend**     | Django 6.0.5 (Python 3.14) |
| **Base de données** | PostgreSQL (dev : SQLite) |
| **Frontend**    | HTML + Tailwind CSS 3     |
| **Serveur**     | Nginx + Gunicorn (prod)   |
| **Cache**       | Redis (prévu)             |
| **Versioning**  | Git + GitHub              |

---

## Structure du Projet

```
upgcexam/
├── config/               # Configuration Django (settings, urls, wsgi, asgi)
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                 # Application principale
│   ├── models.py         # Modèles de données (8 tables)
│   ├── views.py          # Vues (inscription, connexion, tableau de bord, etc.)
│   ├── urls.py           # Routes de l'application
│   ├── admin.py          # Interface d'administration Django
│   ├── templates/core/   # Templates HTML
│   │   ├── base.html
│   │   ├── accueil.html          # Page d'accueil
│   │   ├── inscription.html      # Inscription (nouveau design 2026)
│   │   ├── login.html            # Connexion (nouveau design 2026)
│   │   ├── verification.html     # Vérification email
│   │   ├── tableau_de_bord.html  # Dashboard étudiant
│   │   ├── admin_dashboard.html  # Dashboard admin
│   │   ├── bibliotheque.html     # Bibliothèque des sujets
│   │   ├── detail_sujet.html     # Détail d'un sujet
│   │   ├── recherche.html        # Recherche avancée
│   │   ├── ajouter_sujet.html    # Ajout de sujet
│   │   ├── modifier_sujet.html   # Modification de sujet
│   │   ├── supprimer_sujet.html  # Confirmation suppression
│   │   └── parametres.html       # Paramètres utilisateur
│   ├── static/core/images/       # Images et assets
│   └── migrations/               # Migrations base de données
├── manage.py
└── README.md
```

---

## Ce qui a été fait ✅

### Base de données — 8 modèles
| Modèle         | Rôle                                      |
|----------------|-------------------------------------------|
| `Filiere`      | Filières académiques (Informatique, Maths…) |
| `Niveau`       | Licence, Master…                          |
| `Matiere`      | Matières liées aux filières               |
| `Utilisateur`  | Profil étendu (rôle, filière, email vérifié) |
| `Sujet`        | Annales (titre, PDF, année, stats…)       |
| `Telechargement` | Log des téléchargements                  |
| `Activite`     | Journal d'activité utilisateur            |
| `Verification` | Codes de vérification email               |

### Pages développées
- ✅ **Page d'accueil** — stats (sujets, filières, années) + sujets populaires
- ✅ **Inscription** — formulaire + vérification email (code 6 chiffres)
- ✅ **Connexion** — authentification Django + redirection
- ✅ **Tableau de bord** — stats personnelles + activités récentes
- ✅ **Bibliothèque** — grille de sujets avec pagination + filtres
- ✅ **Détail sujet** — visualisation + téléchargement + sujets similaires
- ✅ **Recherche** — recherche avec suggestions + docs populaires
- ✅ **Ajout de sujet** — upload PDF avec validation
- ✅ **Administration** — stats globales, validation des sujets, gestion
- ✅ **Paramètres** — modification profil + mot de passe
- ✅ **Vérification email** — validation du code

### Design
- ✅ Tailwind CSS 3 + Google Fonts Inter
- ✅ Design responsive (mobile first)
- ✅ Pages inscription/connexion modernisées (24 mai 2026)

---

## Roadmap 🗺️

### Phase 1 : Fondations ✅
- [x] Modèles de données
- [x] Authentification (inscription, connexion, vérification email)
- [x] Pages CRUD sujets
- [x] Recherche et filtres
- [x] Dashboard admin

### Phase 2 : Améliorations 🔜
- [ ] **Mot de passe oublié** — réinitialisation par email
- [ ] **Page d'accueil** — finir le design (nouveau template Claude ?)
- [ ] **Profil utilisateur** — avatar, bio, filière éditables
- [ ] **Notifications** — email pour validation de sujet, nouveau sujet
- [ ] **Favoris** — marquer des sujets en favoris
- [ ] **Commentaires** — noter/commenter un sujet
- [ ] **Leaderboard** — classement des contributeurs

### Phase 3 : Production 🚀
- [ ] Déploiement Nginx + Gunicorn + PostgreSQL
- [ ] Cache Redis
- [ ] Domaine personnalisé (ex: upgcexam.ci)
- [ ] Certificat SSL (Let's Encrypt)
- [ ] Sauvegarde automatique base de données

### Phase 4 : Scale 📈
- [ ] API REST (Django REST Framework)
- [ ] Application mobile (Flutter/React Native)
- [ ] Contribution enseignants (upload direct)
- [ ] Statistiques avancées (graphiques)
- [ ] Mode hors-ligne (PWA)

---

## Installation

```bash
# 1. Cloner
git clone https://github.com/TANNOU-dev/upgcexam.git
cd upgcexam

# 2. Environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 3. Dépendances
pip install -r requirements.txt

# 4. Base de données
python manage.py migrate

# 5. Données initiales (filières, niveaux)
python manage.py loaddata initial_data.json

# 6. Super admin
python manage.py createsuperuser

# 7. Lancement
python manage.py runserver
```

---

## Équipe

| Rôle                | Personne                        | Contact                    |
|---------------------|---------------------------------|----------------------------|
| **Fondateur**       | Yao Mondésir (+225 0500032981)  | Master UPGC — à l'initiative du projet |
| **Développeur**     | Tannou Abou (@Tannouabou)       | Master 1 Info UPGC — Korhogo |
| **Assistant IA**    | Nova                            | Développement & conseil technique |

---

## Licence

Projet académique — Université Péléforo Gon Coulibaly (UPGC), Korhogo.
