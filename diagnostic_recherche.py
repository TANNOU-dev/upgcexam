#!/usr/bin/env python3
"""Diagnostic du bug de recherche UPGCExam"""
import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()
from django.db.models import Count

from core.models import Sujet, Filiere

def afficher_titre(t):
    print(f"\n{'='*60}")
    print(f"  {t}")
    print(f"{'='*60}")

# Étape 1 : Stats
afficher_titre("📊 ÉTAT DE LA BASE")
print(f"Nombre total de sujets : {Sujet.objects.count()}")
print(f"Nombre de filières     : {Filiere.objects.count()}")

print(f"\nRépartition par statut :")
for s, c in Sujet.objects.values_list("statut").distinct().annotate(c=Count("id")):
    print(f"  - {s}: {c} sujets")

print(f"\nRépartition par visibilité :")
for v, c in Sujet.objects.values_list("visibilite").distinct().annotate(c=Count("id")):
    print(f"  - {v}: {c} sujets")

# Étape 2 : Sujets visibles
afficher_titre("👀 SUJETS VISIBLES (statut=actif + visibilite=visible)")
qs = Sujet.objects.filter(statut="actif", visibilite="visible").select_related("filiere", "matiere")
print(f"Nombre : {qs.count()}")
for s in qs:
    m = s.matiere.nom if s.matiere else "?"
    f = s.filiere.nom if s.filiere else "?"
    print(f"  [{s.id}] {s.titre[:50]}")
    print(f"         Filière={f} | Matière={m} | auteur_nom='{s.auteur_nom}'")

# Étape 3 : Test recherche exacte
afficher_titre("🔎 TEST RECHERCHE TEXTE")
query = input("Entre le nom du sujet que tu cherches (ou 'tous'): ").strip()

from django.db.models import Q
if query == "tous":
    for terme in ["info", "math", "examen", "tp", "devoir", "Licence", "Master"]:
        r = qs.filter(
            Q(titre__icontains=terme) |
            Q(description__icontains=terme) |
            Q(auteur_nom__icontains=terme) |
            Q(matiere__nom__icontains=terme)
        )
        if r.count() > 0:
            print(f"  ✅ '{terme}' → {r.count()} résultat(s)")
        else:
            print(f"  ❌ '{terme}' → 0 résultat")
else:
    r = qs.filter(
        Q(titre__icontains=query) |
        Q(description__icontains=query) |
        Q(auteur_nom__icontains=query) |
        Q(matiere__nom__icontains=query)
    )
    print(f"Résultats pour '{query}': {r.count()}")
    if r.count() > 0:
        for s in r:
            m = s.matiere.nom if s.matiere else "?"
            f = s.filiere.nom if s.filiere else "?"
            print(f"  ✅ [{s.id}] {s.titre} ({f} - {m})")
    else:
        # Test sans filtre
        print(f"\n  🔧 Test SANS les filtres statut/visibilite :")
        r2 = Sujet.objects.filter(
            Q(titre__icontains=query) |
            Q(description__icontains=query)
        )
        print(f"  Résultats sans filtre: {r2.count()}")
        for s in r2:
            print(f"     [{s.id}] {s.titre} (statut={s.statut}, visibilite={s.visibilite})")

print(f"\n✅ Diagnostic terminé ! Copie les résultats et envoie-les à Nova.")
