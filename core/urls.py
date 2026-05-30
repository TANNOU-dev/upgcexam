from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('sujets/', views.bibliotheque, name='bibliotheque'),
    path('sujets/recherche/', views.recherche, name='recherche'),
    path('sujets/ajouter/', views.ajouter_sujet, name='ajouter_sujet'),
    path('sujets/modifier/<int:sujet_id>/', views.modifier_sujet, name='modifier_sujet'),
    path('sujets/<int:sujet_id>/', views.detail_sujet, name='detail_sujet'),
    path('sujets/telecharger/<int:sujet_id>/', views.telecharger_sujet, name='telecharger_sujet'),
    path('administration/', views.admin_dashboard, name='admin_dashboard'),
    path('sujets/supprimer/<int:sujet_id>/', views.supprimer_sujet, name='supprimer_sujet'),
    path('sujets/basculer-visibilite/<int:sujet_id>/', views.basculer_visibilite, name='basculer_visibilite'),
    path('connexion/', views.connexion, name='connexion'),
    path('inscription/', views.inscription, name='inscription'),
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord'),
    path('verification/', views.verification, name='verification'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('parametres/', views.parametres, name='parametres'),
    # Mot de passe oublié
    path('mot-de-passe-oublie/', auth_views.PasswordResetView.as_view(
        template_name='core/password_reset.html',
        email_template_name='core/password_reset_email.html',
        subject_template_name='core/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('mot-de-passe-oublie/envoye/', auth_views.PasswordResetDoneView.as_view(
        template_name='core/password_reset_done.html',
    ), name='password_reset_done'),
    path('mot-de-passe-oublie/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='core/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('mot-de-passe-oublie/termine/', auth_views.PasswordResetCompleteView.as_view(
        template_name='core/password_reset_complete.html',
    ), name='password_reset_complete'),
    # Admin
    path('administration/utilisateurs/', views.admin_utilisateurs, name='admin_utilisateurs'),
    path('administration/filieres/', views.admin_filieres, name='admin_filieres'),
    path('administration/matieres/', views.admin_matieres, name='admin_matieres'),
    path('administration/niveaux/', views.admin_niveaux, name='admin_niveaux'),
    path('administration/logs/', views.admin_logs, name='admin_logs'),
    path('administration/sujets/', views.admin_sujets, name='admin_sujets'),
    path('administration/sujets/voir-pdf/<int:sujet_id>/', views.admin_voir_sujet_pdf, name='admin_voir_sujet_pdf'),
    path('administration/verifications/', views.admin_verifications, name='admin_verifications'),
    path('pwa/subscribe/', views.push_subscribe, name='push_subscribe'),
]
