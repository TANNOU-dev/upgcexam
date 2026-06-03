"""
Crée ou met à jour les filières avec leur nom et code.
Usage : python manage.py shell < scripts/update_filiere_codes.py
"""
from core.models import Filiere

# Dictionnaire : nom de la filière → code
FILIERES = {
    "Agriculture": "AGRI",
    "Économie et Gestion Agropastorale": "GAP",
    "Zootechnie": "ZOO",
    "Lettres Modernes": "LM",
    "Anglais": "ANG",
    "Sciences de l'Information et de la Communication": "SIC",
    "Médecine et spécialités médicales": "MED",
    "Chirurgie et spécialités chirurgicales": "CHIR",
    "Santé de la mère et de l'enfant": "SME",
    "Sciences fondamentales et biologiques": "SFB",
    "Santé publique et spécialités connexes": "SP",
    "Géosciences": "GEO",
    "Biochimie-Génétique": "BG",
    "Biologie Végétale": "BV",
    "Biologie Animale": "BA",
    "Mathématiques": "MATH",
    "Physique Chimie": "PC",
    "Informatique": "INFO",
    "Mathématiques-Informatique, Physique Chimie": "MPC",
    "Géographie": "GEOG",
    "Droit": "DRT",
    "Sociologie": "SOCIO",
    "Économie": "ECO",
    "Histoire": "HIST",
    "Philosophie": "PHILO",
}

cree, mis_a_jour = 0, 0

for nom, code in FILIERES.items():
    filiere, created = Filiere.objects.update_or_create(
        nom=nom,
        defaults={"code": code},
    )
    if created:
        print(f"✅ Créée : {nom} → {code}")
        cree += 1
    else:
        print(f"♻️  Mise à jour : {nom} → {code}")
        mis_a_jour += 1

print(f"\nRésultat : {cree} créée(s), {mis_a_jour} mise(s) à jour")
