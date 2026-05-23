from django.urls import path
from . import views

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('sujets/', views.bibliotheque, name='bibliotheque'),
    path('sujets/recherche/', views.recherche, name='recherche'),
    path('sujets/ajouter/', views.ajouter_sujet, name='ajouter_sujet'),
    path('sujets/modifier/<int:sujet_id>/', views.modifier_sujet, name='modifier_sujet'),
    path('sujets/<int:sujet_id>/', views.detail_sujet, name='detail_sujet'),
    path('administration/', views.admin_dashboard, name='admin_dashboard'),
    path('sujets/supprimer/<int:sujet_id>/', views.supprimer_sujet, name='supprimer_sujet'),
    path('connexion/', views.connexion, name='connexion'),
    path('inscription/', views.inscription, name='inscription'),
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord'),
    path('verification/', views.verification, name='verification'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('parametres/', views.parametres, name='parametres'),
]
