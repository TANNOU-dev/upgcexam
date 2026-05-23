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
            "deconnexion": "/connexion/?next=/deconnexion/",
            "ajouter_sujet": "/connexion/?next=/ajouter-un-sujet/",
        }

        for name, location in expected.items():
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], location)

    def test_login_uses_safe_next_url(self):
        User.objects.create_user(username="etudiant", password="Motdepasse12345")

        response = self.client.post(
            f"{reverse('connexion')}?next={reverse('bibliotheque')}",
            {"username": "etudiant", "password": "Motdepasse12345"},
        )

        self.assertRedirects(response, reverse("bibliotheque"))

    def test_login_ignores_external_next_url(self):
        User.objects.create_user(username="etudiant", password="Motdepasse12345")

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

    def test_add_subject_page_is_accessible_to_authenticated_users(self):
        user = User.objects.create_user(username="etudiant", password="Motdepasse12345")
        self.client.force_login(user)

        response = self.client.get(reverse("ajouter_sujet"))

        self.assertEqual(response.status_code, 200)

    def test_add_subject_creates_subject_with_existing_data(self):
        user = User.objects.create_user(username="etudiant", password="Motdepasse12345")
        filiere = Filiere.objects.create(nom="Mathématiques-Informatique", code="MI")
        matiere = Matiere.objects.create(nom="Calcul Différentiel", filiere=filiere)
        Niveau.objects.create(nom="L1")
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
                "annee_academique": "2025-2026",
                "fichier_pdf": pdf,
            },
        )

        self.assertRedirects(response, reverse("bibliotheque"))
        self.assertTrue(Sujet.objects.filter(titre="Algèbre Linéaire - Examen Final").exists())
