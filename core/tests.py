from datetime import timedelta
import shutil

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Filiere, Matiere, Niveau, Sujet, Utilisateur, Verification


@override_settings(ALLOWED_HOSTS=["testserver"], MEDIA_ROOT="/tmp/upgcexam-test-media")
class CoreViewsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree("/tmp/upgcexam-test-media", ignore_errors=True)

    def test_public_pages_are_accessible(self):
        for name in ["accueil", "bibliotheque", "connexion", "inscription"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)

    def test_private_pages_redirect_anonymous_users_to_login(self):
        expected = {
            "tableau_de_bord": "/connexion/?next=/tableau-de-bord/",
            "parametres": "/connexion/?next=/parametres/",
            "ajouter_sujet": "/connexion/?next=/sujets/ajouter/",
        }

        for name, location in expected.items():
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], location)

    def test_deconnexion_requires_post(self):
        user = User.objects.create_user(username="etudiant", password="Motdepasse12345")
        self.client.force_login(user)
        get_response = self.client.get(reverse("deconnexion"))
        self.assertEqual(get_response.status_code, 405)
        post_response = self.client.post(reverse("deconnexion"))
        self.assertRedirects(post_response, reverse("accueil"))

    def _login_user(self, username="etudiant", password="Motdepasse12345"):
        user = User.objects.create_user(username=username, password=password)
        Utilisateur.objects.create(user=user, email_verifie=True)
        return user

    def test_login_uses_safe_next_url(self):
        self._login_user()

        response = self.client.post(
            f"{reverse('connexion')}?next={reverse('bibliotheque')}",
            {"username": "etudiant", "password": "Motdepasse12345"},
        )

        self.assertRedirects(response, reverse("bibliotheque"))

    def test_login_ignores_external_next_url(self):
        self._login_user()

        response = self.client.post(
            f"{reverse('connexion')}?next=https://example.com",
            {"username": "etudiant", "password": "Motdepasse12345"},
        )

        self.assertRedirects(response, reverse("tableau_de_bord"))

    def test_registration_creates_user_profile_and_verification(self):
        response = self.client.post(
            reverse("inscription"),
            {
                "username": "nouveau",
                "email": "nouveau@example.com",
                "password": "Motdepasse12345",
                "password2": "Motdepasse12345",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("verification"))
        user = User.objects.get(username="nouveau")
        self.assertTrue(Utilisateur.objects.filter(user=user).exists())
        self.assertTrue(Verification.objects.filter(email="nouveau@example.com").exists())

    def test_verification_marks_profile_verified_and_logs_user_in(self):
        user = User.objects.create_user(
            username="nouveau",
            email="nouveau@example.com",
            password="Motdepasse12345",
        )
        Utilisateur.objects.create(user=user)
        Verification.objects.create(
            email="nouveau@example.com",
            code="123456",
            expire_le=timezone.now() + timedelta(minutes=10),
        )
        session = self.client.session
        session["email_a_verifier"] = "nouveau@example.com"
        session.save()

        response = self.client.post(reverse("verification"), {"code": "123456"})

        self.assertRedirects(response, reverse("tableau_de_bord"))
        user.refresh_from_db()
        self.assertTrue(user.profil.email_verifie)
        self.assertTrue(Verification.objects.get(email=user.email).utilise)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_add_subject_page_requires_verified_email(self):
        user = User.objects.create_user(username="etudiant", password="Motdepasse12345")
        Utilisateur.objects.create(user=user, email_verifie=False)
        self.client.force_login(user)

        response = self.client.get(reverse("ajouter_sujet"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("verification"), response["Location"])
        self.assertIn("next=", response["Location"])

    def test_add_subject_creates_subject_with_existing_data(self):
        user = User.objects.create_user(username="etudiant", password="Motdepasse12345")
        Utilisateur.objects.create(user=user, email_verifie=True)
        filiere = Filiere.objects.create(nom="Mathématiques-Informatique", code="MI")
        matiere = Matiere.objects.create(nom="Calcul Différentiel", filiere=filiere)
        niveau = Niveau.objects.create(nom="L1")
        self.client.force_login(user)
        pdf = SimpleUploadedFile(
            "sujet.pdf",
            b"%PDF-1.4\n%UPGCExam test\n",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("ajouter_sujet"),
            {
                "titre": "Algèbre Linéaire - Examen Final",
                "filiere": str(filiere.id),
                "matiere": str(matiere.id),
                "niveau": str(niveau.id),
                "annee_academique": "2025-2026",
                "fichier_pdf": pdf,
            },
        )

        self.assertRedirects(response, reverse("bibliotheque"))
        sujet = Sujet.objects.get(titre="Algèbre Linéaire - Examen Final")
        self.assertEqual(sujet.statut, "en_attente")

    def _create_sujet(self, owner):
        filiere = Filiere.objects.create(nom="Informatique", code="INF")
        matiere = Matiere.objects.create(nom="Algo", filiere=filiere)
        niveau = Niveau.objects.create(nom="L2")
        pdf = SimpleUploadedFile("s.pdf", b"%PDF-1.4", content_type="application/pdf")
        return Sujet.objects.create(
            titre="Test Sujet",
            filiere=filiere,
            matiere=matiere,
            niveau=niveau,
            annee_academique="2024-2025",
            fichier_pdf=pdf,
            publie_par=owner,
            statut="actif",
        )

    def test_owner_can_access_modify_page(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(owner)

        response = self.client.get(reverse("modifier_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_modify_sujet(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        intrus = User.objects.create_user(username="intrus", password="Pass12345")
        Utilisateur.objects.create(user=owner, email_verifie=True)
        Utilisateur.objects.create(user=intrus, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(intrus)

        response = self.client.get(reverse("modifier_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_sujet(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(owner)

        response = self.client.get(reverse("supprimer_sujet", args=[sujet.id]))

        self.assertRedirects(response, reverse("bibliotheque"))

    def test_staff_can_delete_sujet(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        admin = User.objects.create_user(username="admin", password="Pass12345", is_staff=True)
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(admin)

        response = self.client.get(reverse("supprimer_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_staff_can_modify_any_sujet(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        admin = User.objects.create_user(username="admin", password="Pass12345", is_staff=True)
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(admin)

        response = self.client.get(reverse("modifier_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_admin_voir_pdf_returns_404_for_non_staff(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        sujet = self._create_sujet(owner)
        self.client.force_login(owner)

        response = self.client.get(reverse("admin_voir_sujet_pdf", args=[sujet.id]))

        self.assertEqual(response.status_code, 404)

    def test_detail_sujet_requires_login(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        sujet = self._create_sujet(owner)

        response = self.client.get(reverse("detail_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("connexion"), response["Location"])
        self.assertIn(f"/sujets/{sujet.id}/", response["Location"])

    def test_detail_sujet_accessible_when_logged_in(self):
        owner = User.objects.create_user(username="proprio", password="Pass12345")
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(owner)

        response = self.client.get(reverse("detail_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_login_after_search_returns_to_detail(self):
        user = self._login_user()
        sujet = self._create_sujet(user)
        detail_url = reverse("detail_sujet", args=[sujet.id])

        self.client.logout()
        response = self.client.post(
            f"{reverse('connexion')}?next={detail_url}",
            {"username": "etudiant", "password": "Motdepasse12345"},
        )

        self.assertRedirects(response, detail_url)
