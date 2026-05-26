# 🔍 Audit UPGCExam — 26 Mai 2026

## ✅ SÉCURITÉ — Satisfaisant

| Point | Statut | Note |
|---|---|---|
| Permissions admin (is_staff) | ✅ | Toutes les vues admin vérifiées |
| Accès aux sujets restreints | ✅ | Filtrés par `_sujets_accessibles()` |
| Upload PDF (magic bytes %PDF-) | ✅ | Vérifié dans `utils.py` |
| Validation CSRF | ✅ | Middleware actif |
| XSS (auto-escaping Django) | ✅ | Templates sécurisés |
| Open redirect (next URL) | ✅ | `safe_next_url()` dans navigation.py |
| Validateurs mot de passe | ✅ | 4 validateurs actifs |
| Taille max upload (10 Mo) | ✅ | Configuré |
| Session/TLS email | ✅ | Configurable via env vars |

**🔴 À corriger (prod) :**
- `SECRET_KEY` = fallback "django-insecure..." → **mettre une vraie clé** via `DJANGO_SECRET_KEY` en prod
- `DEBUG = True` par défaut → désactiver en prod via `DJANGO_DEBUG=false`

---

## ✅ LOGIQUE MÉTIER — Satisfaisant

| Point | Statut | Note |
|---|---|---|
| Flow statut (en_attente → actif → archive) | ✅ | Cohérent |
| Ajout étudiant → en_attente → admin valide | ✅ | Fonctionnel |
| Modification étudiant → en_attente → admin re-valide | ✅ | **Corrigé aujourd'hui** |
| Admin modifie → publié directement | ✅ | Fonctionnel |
| Visibilité restreinte (admin only) | ✅ | Filtré + champ caché |
| Archivage (admin only) | ✅ | **Corrigé aujourd'hui** |
| Messages d'action visibles | ✅ | **Corrigé aujourd'hui** |

---

## ⚠️ CODE QUALITÉ — À nettoyer

| Problème | Sévérité | Action |
|---|---|---|
| `_matieres_par_filiere()` inutilisée | 🟡 Faible | Supprimer la fonction |
| `_creer_code_verification()` en double | 🟡 Faible | Utiliser `generer_code_verification()` d'`utils.py` |
| CSS/JS inline dans tous les templates | 🟡 Faible | Déplacer en fichiers statiques |
| `ajouter_sujet` / `modifier_sujet` similaires | 🟡 Faible | Possible refacto mais pas prioritaire |
| `Utilisateur.role` jamais utilisé | 🟢 Info | Champ orphelin (permissions via is_staff) |

---

## ⚠️ PERFORMANCE — À optimiser

| Problème | Sévérité | Action |
|---|---|---|
| `admin_verifications` sans `select_related` | 🟡 Moyen | Ajouter `.select_related('user')` |
| `bibliotheque()` requêtes redondantes | 🟡 Faible | Mettre en cache les stats (count, annees) |

---

## 📋 PLAN D'ACTION PRIORITAIRE

### Avant mise en production
1. 🔴 Configurer `SECRET_KEY` via variable d'environnement
2. 🔴 Désactiver `DEBUG` en production
3. 🔴 Utiliser une vraie base PostgreSQL au lieu de SQLite
4. 🟡 Activer HTTPS (nginx + certbot)

### Nettoyage code (quand tu veux)
1. 🟡 Supprimer `_matieres_par_filiere()` et `_creer_code_verification()`
2. 🟡 Ajouter `select_related('user')` dans `admin_verifications()`
3. 🟢 Optionnel : déplacer CSS/JS en fichiers statiques
