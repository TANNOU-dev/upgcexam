from django.urls import path
from .views import (
    auth,
    sujets,
    admin,
    pwa,
)

urlpatterns = [
    path('', sujets.accueil, name='accueil'),
    path('sujets/', sujets.bibliotheque, name='bibliotheque'),
    path('sujets/recherche/', sujets.recherche, name='recherche'),
    path('sujets/mes-sujets/', sujets.mes_sujets, name='mes_sujets'),
    path('sujets/ajouter/', sujets.ajouter_sujet, name='ajouter_sujet'),
    path('sujets/modifier/<int:sujet_id>/', sujets.modifier_sujet, name='modifier_sujet'),
    path('sujets/<int:sujet_id>/', sujets.detail_sujet, name='detail_sujet'),
    path('sujets/telecharger/<int:sujet_id>/', sujets.telecharger_sujet, name='telecharger_sujet'),
    path('administration/', admin.admin_dashboard, name='admin_dashboard'),
    path('sujets/supprimer/<int:sujet_id>/', sujets.supprimer_sujet, name='supprimer_sujet'),
    path('sujets/basculer-visibilite/<int:sujet_id>/', sujets.basculer_visibilite, name='basculer_visibilite'),
    path('connexion/', auth.connexion, name='connexion'),
    path('inscription/', auth.inscription, name='inscription'),
    path('tableau-de-bord/', admin.tableau_de_bord, name='tableau_de_bord'),
    path('api/mon-activite/', admin.mon_activite_json, name='mon_activite_json'),
    path('verification/', auth.verification, name='verification'),
    path('deconnexion/', auth.deconnexion, name='deconnexion'),
    path('parametres/', auth.parametres, name='parametres'),
    # Mot de passe oublié (flux avec code de vérification)
    path('mot-de-passe-oublie/', auth.password_reset_envoyer, name='password_reset'),
    path('mot-de-passe-oublie/code/', auth.password_reset_code, name='password_reset_code'),
    path('mot-de-passe-oublie/nouveau/', auth.password_reset_new, name='password_reset_new'),
    # Admin
    path('administration/utilisateurs/', admin.admin_utilisateurs, name='admin_utilisateurs'),
    path('administration/filieres/', admin.admin_filieres, name='admin_filieres'),
    path('administration/matieres/', admin.admin_matieres, name='admin_matieres'),
    path('administration/niveaux/', admin.admin_niveaux, name='admin_niveaux'),
    path('administration/logs/', admin.admin_logs, name='admin_logs'),
    path('administration/sujets/', admin.admin_sujets, name='admin_sujets'),
    path('administration/sujets/voir-pdf/<int:sujet_id>/', admin.admin_voir_sujet_pdf, name='admin_voir_sujet_pdf'),
    path('administration/presences/', admin.admin_presences, name='admin_presences'),
    path('administration/verifications/', admin.admin_verifications, name='admin_verifications'),
    path('pwa/subscribe/', pwa.push_subscribe, name='push_subscribe'),
]
