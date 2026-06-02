from datetime import timedelta
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .adapters import UPGCExamSocialAdapter


import os
import hashlib

def _test_password(username="default"):
    """Generate deterministic test password without hardcoded secrets.
    Override via UPGC_TEST_PASSWORD env var for CI/CD pipelines."""
    env_pwd = os.environ.get('UPGC_TEST_PASSWORD')
    if env_pwd:
        return env_pwd
    raw = f"upgx_test::{username}::2026"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

from .models import Activite, Filiere, Matiere, Niveau, PushSubscription, Sujet, Utilisateur, Verification


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
        user = User.objects.create_user(username="etudiant", password=_test_password("etudiant"))
        self.client.force_login(user)
        get_response = self.client.get(reverse("deconnexion"))
        self.assertEqual(get_response.status_code, 405)
        post_response = self.client.post(reverse("deconnexion"))
        self.assertRedirects(post_response, reverse("accueil"))

    def _login_user(self, username="etudiant", password=_test_password("etudiant")):
        user = User.objects.create_user(username=username, password=password)
        Utilisateur.objects.create(user=user, email_verifie=True)
        return user

    def test_login_uses_safe_next_url(self):
        self._login_user()

        response = self.client.post(
            f"{reverse('connexion')}?next={reverse('bibliotheque')}",
            {"username": "etudiant", "password": _test_password("etudiant")},
        )

        self.assertRedirects(response, reverse("bibliotheque"))

    def test_login_ignores_backslash_external_next_url(self):
        self._login_user()

        response = self.client.post(
            f"{reverse('connexion')}?next=/\\example.com",
            {"username": "etudiant", "password": _test_password("etudiant")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("tableau_de_bord"))

    def test_login_ignores_external_next_url(self):
        self._login_user()

        response = self.client.post(
            f"{reverse('connexion')}?next=https://example.com",
            {"username": "etudiant", "password": _test_password("etudiant")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("tableau_de_bord"))

    @patch("allauth.socialaccount.adapter.DefaultSocialAccountAdapter.save_user")
    def test_social_signup_marks_provider_verified_email_as_verified(self, mocked_save_user):
        user = User.objects.create_user(username="google-user", email="google@example.com")
        mocked_save_user.return_value = user
        sociallogin = SimpleNamespace(
            email_addresses=[SimpleNamespace(email=user.email, verified=True)]
        )

        UPGCExamSocialAdapter().save_user(None, sociallogin)

        self.assertTrue(user.profil.email_verifie)

    def test_registration_creates_user_profile_and_verification(self):
        response = self.client.post(
            reverse("inscription"),
            {
                "username": "nouveau",
                "email": "nouveau@example.com",
                "password": _test_password("etudiant"),
                "password2": _test_password("etudiant"),
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
            password=_test_password("etudiant"),
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

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("tableau_de_bord"))
        user.refresh_from_db()
        self.assertTrue(user.profil.email_verifie)
        self.assertTrue(Verification.objects.get(email=user.email).utilise)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_add_subject_page_requires_verified_email(self):
        user = User.objects.create_user(username="etudiant", password=_test_password("etudiant"))
        Utilisateur.objects.create(user=user, email_verifie=False)
        self.client.force_login(user)

        response = self.client.get(reverse("ajouter_sujet"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("verification"), response["Location"])
        self.assertIn("next=", response["Location"])

    def test_add_subject_creates_subject_with_existing_data(self):
        user = User.objects.create_user(username="etudiant", password=_test_password("etudiant"))
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
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(owner)

        response = self.client.get(reverse("modifier_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_modify_sujet(self):
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
        intrus = User.objects.create_user(username="intrus", password=_test_password("user"))
        Utilisateur.objects.create(user=owner, email_verifie=True)
        Utilisateur.objects.create(user=intrus, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(intrus)

        response = self.client.get(reverse("modifier_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_sujet(self):
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(owner)

        response = self.client.get(reverse("supprimer_sujet", args=[sujet.id]))

        self.assertRedirects(response, reverse("bibliotheque"))

    def test_staff_can_delete_sujet(self):
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
        admin = User.objects.create_user(username="admin", password=_test_password("user"), is_staff=True)
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(admin)

        response = self.client.get(reverse("supprimer_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_staff_can_modify_any_sujet(self):
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
        admin = User.objects.create_user(username="admin", password=_test_password("user"), is_staff=True)
        Utilisateur.objects.create(user=owner, email_verifie=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(admin)

        response = self.client.get(reverse("modifier_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_admin_voir_pdf_redirects_non_staff(self):
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
        sujet = self._create_sujet(owner)
        self.client.force_login(owner)

        response = self.client.get(reverse("admin_voir_sujet_pdf", args=[sujet.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("tableau_de_bord"))

    def test_detail_sujet_publicly_accessible(self):
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
        sujet = self._create_sujet(owner)

        response = self.client.get(reverse("detail_sujet", args=[sujet.id]))

        self.assertEqual(response.status_code, 200)

    def test_detail_sujet_accessible_when_logged_in(self):
        owner = User.objects.create_user(username="proprio", password=_test_password("user"))
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
            {"username": "etudiant", "password": _test_password("etudiant")},
        )

        self.assertRedirects(response, detail_url)

    def test_wrong_verification_code_increments_attempt_counter(self):
        verification = Verification.objects.create(
            email="nouveau@example.com",
            code="123456",
            expire_le=timezone.now() + timedelta(minutes=10),
        )
        session = self.client.session
        session["email_a_verifier"] = verification.email
        session.save()

        response = self.client.post(reverse("verification"), {"code": "000000"})

        self.assertEqual(response.status_code, 200)
        verification.refresh_from_db()
        self.assertEqual(verification.tentatives, 1)

    def test_password_reset_code_allows_form_get_then_password_update(self):
        user = User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password=_test_password("old"),
        )
        Verification.objects.create(
            email=user.email,
            code="123456",
            usage=Verification.USAGE_PASSWORD_RESET,
            expire_le=timezone.now() + timedelta(minutes=10),
        )
        session = self.client.session
        session["reset_email"] = user.email
        session.save()

        response = self.client.post(reverse("password_reset_code"), {"code": "123456"})
        self.assertRedirects(response, reverse("password_reset_new"))

        response = self.client.get(reverse("password_reset_new"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("password_reset_new"),
            {
                "password": _test_password("new"),
                "password2": _test_password("new"),
            },
        )
        self.assertRedirects(response, reverse("connexion"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(_test_password("new")))

    def test_add_subject_without_pdf_is_rejected_without_server_error(self):
        user = User.objects.create_user(username="etudiant", password=_test_password("etudiant"))
        Utilisateur.objects.create(user=user, email_verifie=True)
        filiere = Filiere.objects.create(nom="Informatique", code="INFO")
        niveau = Niveau.objects.create(nom="L1")
        self.client.force_login(user)

        response = self.client.post(
            reverse("ajouter_sujet"),
            {
                "titre": "Sujet incomplet",
                "filiere": str(filiere.id),
                "matiere": "Algorithmique",
                "niveau": str(niveau.id),
                "annee_academique": "2025-2026",
            },
        )

        self.assertRedirects(response, reverse("ajouter_sujet"))
        self.assertFalse(Sujet.objects.filter(titre="Sujet incomplet").exists())

    def test_staff_cannot_mutate_another_user_account(self):
        staff = User.objects.create_user(username="staff", password=_test_password("user"), is_staff=True)
        target = User.objects.create_user(username="target", password=_test_password("user"))
        self.client.force_login(staff)

        response = self.client.post(
            reverse("admin_utilisateurs"),
            {"action": "toggle_active", "user_id": target.id},
        )

        self.assertRedirects(response, reverse("admin_utilisateurs"))
        target.refresh_from_db()
        self.assertTrue(target.is_active)

    def test_superuser_can_mutate_another_user_account(self):
        admin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password=_test_password("user"),
        )
        target = User.objects.create_user(username="target", password=_test_password("user"))
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin_utilisateurs"),
            {"action": "toggle_active", "user_id": target.id},
        )

        self.assertRedirects(response, reverse("admin_utilisateurs"))
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_group_management_requires_superuser(self):
        staff = User.objects.create_user(username="staff", password=_test_password("user"), is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(reverse("admin_groupes"))

        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_admin_bulk_archive_ignores_invalid_and_unknown_ids(self):
        owner = User.objects.create_user(username="owner", password=_test_password("user"))
        admin = User.objects.create_user(username="staff", password=_test_password("user"), is_staff=True)
        sujet = self._create_sujet(owner)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin_sujets"),
            {"action": "archiver", "sujets_ids": [str(sujet.id), "invalid", "999999"]},
        )

        self.assertRedirects(response, reverse("admin_sujets"))
        sujet.refresh_from_db()
        self.assertEqual(sujet.statut, "archive")
        self.assertEqual(
            Activite.objects.filter(type="archivage", sujet=sujet).count(),
            1,
        )

    def test_admin_bulk_validation_creates_activity(self):
        owner = User.objects.create_user(username="owner", password=_test_password("user"))
        admin = User.objects.create_user(username="staff", password=_test_password("user"), is_staff=True)
        sujet = self._create_sujet(owner)
        sujet.statut = "en_attente"
        sujet.save(update_fields=["statut"])
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin_sujets"),
            {"action": "valider", "sujets_ids": [str(sujet.id)]},
        )

        self.assertRedirects(response, reverse("admin_sujets"))
        sujet.refresh_from_db()
        self.assertEqual(sujet.statut, "actif")
        self.assertTrue(Activite.objects.filter(type="validation", sujet=sujet).exists())

    def test_push_subscription_rejects_invalid_payload_without_leaking_details(self):
        user = User.objects.create_user(username="push-user", password=_test_password("user"))
        self.client.force_login(user)

        response = self.client.post(
            reverse("push_subscribe"),
            data=json.dumps({"endpoint": "invalid", "keys": {}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"ok": False, "error": "Abonnement push invalide."})

    def test_push_subscription_accepts_valid_payload(self):
        user = User.objects.create_user(username="push-user", password=_test_password("user"))
        self.client.force_login(user)
        payload = {
            "endpoint": "https://push.example.com/subscription",
            "keys": {"auth": "auth-key", "p256dh": "public-key"},
        }

        response = self.client.post(
            reverse("push_subscribe"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(utilisateur=user).exists())

    def test_service_worker_is_served_from_root_scope(self):
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        response.close()


    def test_add_subject_rejects_forged_catalog_id_without_server_error(self):
        user = self._login_user()
        niveau = Niveau.objects.create(nom="L3")
        self.client.force_login(user)
        pdf = SimpleUploadedFile("sujet.pdf", b"%PDF-1.4", content_type="application/pdf")

        response = self.client.post(
            reverse("ajouter_sujet"),
            {
                "titre": "Sujet forgé",
                "filiere": "invalide",
                "matiere": "Sécurité",
                "niveau": str(niveau.id),
                "annee_academique": "2025-2026",
                "fichier_pdf": pdf,
            },
        )

        self.assertRedirects(response, reverse("ajouter_sujet"))
        self.assertFalse(Sujet.objects.filter(titre="Sujet forgé").exists())

    def test_subject_model_validation_rejects_fake_pdf(self):
        filiere = Filiere.objects.create(nom="Informatique", code="INFO")
        matiere = Matiere.objects.create(nom="Sécurité", filiere=filiere)
        niveau = Niveau.objects.create(nom="L3")
        sujet = Sujet(
            titre="Faux PDF",
            filiere=filiere,
            matiere=matiere,
            niveau=niveau,
            annee_academique="2025-2026",
            fichier_pdf=SimpleUploadedFile("fake.pdf", b"texte", content_type="application/pdf"),
        )

        with self.assertRaises(ValidationError):
            sujet.full_clean()

    def test_subject_model_validation_rejects_mismatched_subject(self):
        owner = User.objects.create_user(username="owner", password=_test_password("user"))
        sujet = self._create_sujet(owner)
        autre_filiere = Filiere.objects.create(nom="Droit", code="DROIT")
        sujet.filiere = autre_filiere

        with self.assertRaises(ValidationError):
            sujet.full_clean()

    def test_subject_pdf_is_deleted_with_queryset(self):
        owner = User.objects.create_user(username="owner", password=_test_password("user"))
        sujet = self._create_sujet(owner)
        pdf_path = Path(sujet.fichier_pdf.path)
        self.assertTrue(pdf_path.exists())

        with self.captureOnCommitCallbacks(execute=True):
            Sujet.objects.filter(pk=sujet.pk).delete()

        self.assertFalse(pdf_path.exists())

    def test_library_ignores_forged_catalog_filter_without_server_error(self):
        response = self.client.get(reverse("bibliotheque"), {"filiere": "invalid"})

        self.assertEqual(response.status_code, 200)

    def test_admin_duplicate_level_is_rejected_without_server_error(self):
        admin = User.objects.create_user(username="staff", password=_test_password("user"), is_staff=True)
        Niveau.objects.create(nom="L1")
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin_niveaux"),
            {"action": "ajouter", "nom": "l1"},
        )

        self.assertRedirects(response, reverse("admin_niveaux"))
        self.assertEqual(Niveau.objects.count(), 1)

    def test_admin_group_permissions_reject_forged_id_without_server_error(self):
        admin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password=_test_password("user"),
        )
        group = Group.objects.create(name="Bibliotheque")
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin_groupes"),
            {
                "action": "modifier_permissions",
                "groupe_id": str(group.id),
                "permissions": ["invalid"],
            },
        )

        self.assertRedirects(response, reverse("admin_groupes"))
