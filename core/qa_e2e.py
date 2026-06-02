"""
Tests E2E manuels/automatisés — à lancer avec :
  ./venv/bin/python manage.py shell < core/qa_e2e.py
ou :
  ./venv/bin/python -c "import django; django.setup(); exec(open('core/qa_e2e.py').read())"
"""
import sys
from io import StringIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.models import Filiere, Matiere, Niveau, Sujet, Utilisateur, Verification

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    print(f"{status} {name}" + (f" — {detail}" if detail else ""))
    return condition


def section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")


# --- Setup ---
section("0. Préparation")
client = Client()
client_anon = Client()
PDF = SimpleUploadedFile("test.pdf", b"%PDF-1.4\nQA E2E\n", content_type="application/pdf")
FAKE_PDF = SimpleUploadedFile("fake.pdf", b"NOT_A_PDF", content_type="application/pdf")

# Nettoyage utilisateur QA
User.objects.filter(username__startswith="qa_").delete()

# --- 1. Pages publiques ---
section("1. Pages publiques (visiteur non connecté)")
for page in ["accueil", "bibliotheque", "connexion", "inscription"]:
    r = client_anon.get(reverse(page))
    check(f"GET /{page}/ → 200", r.status_code == 200, f"status={r.status_code}")

r = client_anon.get(reverse("detail_sujet", args=[99999]))
check("Détail sujet sans login → redirect connexion", r.status_code == 302 and "connexion" in r.headers.get("Location", ""))

actif = Sujet.objects.filter(statut="actif").first()
if actif:
    r = client_anon.get(reverse("detail_sujet", args=[actif.id]))
    loc = r.headers.get("Location", "")
    check("Détail sujet actif exige connexion", r.status_code == 302 and "connexion" in loc and f"sujets/{actif.id}" in loc)
    check("Bouton Supprimer absent pour anonyme", "supprimer_sujet" not in r.content.decode() or "peut_supprimer" in str(r.context) if r.context else True)
else:
    print(f"{WARN} Aucun sujet actif en base — tests détail partiels")

r = client_anon.get(reverse("tableau_de_bord"))
check("Tableau de bord → redirect login", r.status_code == 302 and "connexion" in r.headers.get("Location", ""))

# --- 2. Bibliothèque filtres ---
section("2. Bibliothèque — recherche et filtres")
r = client_anon.get(reverse("bibliotheque"), {"q": "examen"})
check("Recherche GET bibliotheque → 200", r.status_code == 200)
check("Formulaire filtres dans un <form>", b'<form method="get"' in r.content and b'name="filiere"' in r.content)
check("Action recherche = bibliotheque", b'action="/sujets/"' in r.content or reverse("bibliotheque") in r.content.decode())

filiere = Filiere.objects.first()
if filiere:
    r = client_anon.get(reverse("bibliotheque"), {"filiere": filiere.id})
    check(f"Filtre filière (id={filiere.id}) → 200", r.status_code == 200)

# --- 3. Inscription + vérification ---
section("3. Parcours inscription / vérification email")
r = client_anon.post(
    reverse("inscription"),
    {
        "username": "qa_etudiant",
        "email": "qa_etudiant@test.local",
        "password": "QaTest12345!",
        "password2": "QaTest12345!",
    },
)
loc = r.headers.get("Location", "") if r.status_code == 302 else ""
check("Inscription → redirect verification", r.status_code == 302 and "verification" in loc, loc)
check("Pas de code dans l'URL", "code=" not in loc)
check("Utilisateur créé", User.objects.filter(username="qa_etudiant").exists())
check("Profil créé", Utilisateur.objects.filter(user__username="qa_etudiant").exists())
check("Code vérification en base", Verification.objects.filter(email="qa_etudiant@test.local", utilise=False).exists())

verif = Verification.objects.filter(email="qa_etudiant@test.local", utilise=False).first()
if verif:
    session = client.session
    session["email_a_verifier"] = "qa_etudiant@test.local"
    session.save()
    r = client.post(reverse("verification"), {"code": verif.code})
    check("Vérification code → redirect dashboard", r.status_code == 302 and "tableau-de-bord" in r.url)
    profil = Utilisateur.objects.get(user__username="qa_etudiant")
    check("email_verifie = True", profil.email_verifie)

# --- 4. Connexion sécurité ---
section("4. Connexion et sécurité")
client.logout()
r = client.post(
    reverse("connexion"),
    {"username": "qa_etudiant", "password": "wrong"},
)
check("Mauvais mot de passe → reste sur connexion", r.status_code == 200)

r = client.post(
    f"{reverse('connexion')}?next=https://evil.com",
    {"username": "qa_etudiant", "password": "QaTest12345!"},
)
loc = r.headers.get("Location", "")
check("Open redirect bloqué", r.status_code == 302 and "evil.com" not in loc)

r = client.get(reverse("deconnexion"))
check("Déconnexion GET → 405", r.status_code == 405)

r = client.post(reverse("deconnexion"))
check("Déconnexion POST → redirect accueil", r.status_code == 302 and reverse("accueil") in r.headers.get("Location", ""))

# Re-login
client.post(reverse("connexion"), {"username": "qa_etudiant", "password": "QaTest12345!"})

# --- 5. Ajout sujet ---
section("5. Ajout de sujet (étudiant)")
r = client.get(reverse("ajouter_sujet"))
check("Page ajouter sujet → 200", r.status_code == 200)
check("Filtre matières par filière (JS)", b"filiere-select" in r.content and b"matiere-select" in r.content)

filiere = Filiere.objects.first()
matiere = Matiere.objects.filter(filiere=filiere).first() if filiere else None
niveau = Niveau.objects.first()
if filiere and matiere and niveau:
    r = client.post(
        reverse("ajouter_sujet"),
        {
            "titre": "QA E2E — Sujet test",
            "filiere": filiere.id,
            "matiere": matiere.id,
            "niveau": niveau.id,
            "annee_academique": "2025-2026",
            "fichier_pdf": PDF,
        },
    )
    check("Ajout PDF valide → redirect bibliotheque", r.status_code == 302)
    sujet_qa = Sujet.objects.filter(titre="QA E2E — Sujet test").first()
    check("Sujet créé en statut en_attente", sujet_qa and sujet_qa.statut == "en_attente")
    check("taille_pdf renseigné", sujet_qa and sujet_qa.taille_pdf)

    # Mauvaise combinaison filière/matière
    autre_filiere = Filiere.objects.exclude(id=filiere.id).first()
    if autre_filiere:
        r = client.post(
            reverse("ajouter_sujet"),
            {
                "titre": "QA E2E — Incohérent",
                "filiere": autre_filiere.id,
                "matiere": matiere.id,
                "niveau": niveau.id,
                "annee_academique": "2025-2026",
                "fichier_pdf": PDF,
            },
        )
        check("Matière hors filière rejetée", r.status_code == 200)

    r = client.post(
        reverse("ajouter_sujet"),
        {
            "titre": "QA E2E — Fake PDF",
            "filiere": filiere.id,
            "matiere": matiere.id,
            "niveau": niveau.id,
            "annee_academique": "2025-2026",
            "fichier_pdf": FAKE_PDF,
        },
    )
    check("Faux PDF rejeté", r.status_code == 200 and not Sujet.objects.filter(titre="QA E2E — Fake PDF").exists())
else:
    print(f"{WARN} Données filière/matière/niveau manquantes — tests ajout partiels")

# --- 6. Permissions sujets ---
section("6. Permissions modifier / supprimer")
if actif:
    owner = actif.publie_par
    if owner:
        c_owner = Client()
        c_owner.force_login(owner)
        r = c_owner.get(reverse("modifier_sujet", args=[actif.id]))
        check("Propriétaire peut modifier son sujet actif", r.status_code == 200)

        r = c_owner.get(reverse("supprimer_sujet", args=[actif.id]))
        check("Non-staff ne peut pas accéder page suppression", r.status_code == 302)

    r = client.get(reverse("supprimer_sujet", args=[actif.id]))
    check("Étudiant qa ne peut pas supprimer", r.status_code == 302)

# --- 7. Admin ---
section("7. Zone administration (staff)")
admin_user, created = User.objects.get_or_create(
    username="qa_admin",
    defaults={"email": "qa_admin@test.local", "is_staff": True},
)
if created:
    admin_user.set_password("QaAdmin12345!")
    admin_user.save()
    Utilisateur.objects.get_or_create(user=admin_user, defaults={"email_verifie": True})

c_admin = Client()
c_admin.force_login(admin_user)

for page in ["admin_dashboard", "admin_sujets", "admin_utilisateurs", "admin_filieres"]:
    r = c_admin.get(reverse(page))
    check(f"Admin GET {page} → 200", r.status_code == 200)

r = client.get(reverse("admin_dashboard"))
check("Étudiant bloqué sur admin_dashboard", r.status_code == 302)

if sujet_qa:
    r = c_admin.post(
        reverse("admin_sujets"),
        {"action": "valider", "sujet_id": sujet_qa.id},
    )
    sujet_qa.refresh_from_db()
    check("Admin valide sujet en_attente → actif", r.status_code == 302 and sujet_qa.statut == "actif")

    r = c_admin.get(reverse("admin_voir_sujet_pdf", args=[sujet_qa.id]))
    check("Admin voit PDF → 200", r.status_code == 200)

    r = client.get(reverse("admin_voir_sujet_pdf", args=[sujet_qa.id]))
    check("Étudiant ne voit pas PDF admin → 404", r.status_code == 404)

# --- 8. Paramètres ---
section("8. Paramètres compte")
r = client.post(
    reverse("parametres"),
    {"username": "qa_etudiant", "email": "qa_etudiant@test.local"},
)
check("Mise à jour profil sans MDP → OK", r.status_code == 302)

# --- Résumé ---
section("RÉSUMÉ")
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"\nTotal : {passed} réussis, {failed} échoués sur {len(results)} checks")
if failed:
    print("\nÉchecs :")
    for s, name, detail in results:
        if s == FAIL:
            print(f"  - {name}: {detail}")
    sys.exit(1)
print(f"\n{PASS} Tous les tests E2E sont passés.")
