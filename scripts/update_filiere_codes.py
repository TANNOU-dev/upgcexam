"""
Mise à jour des codes filières — version corrigée avec les noms réels de la base.
Usage : python manage.py shell < scripts/update_filiere_codes.py
"""
from core.models import Filiere

# Dictionnaire : nom EXACT dans la base → code
CODES = {
    "Agriculture": "AGRI",
    "Économie et Gestion Agropastorale": "GAP",
    "Zootechnie": "ZOO",
    "Lettres Modernes": "LM",
    "Anglais": "ANG",
    "Sciences de l'Information et de la Communication": "SIC",
    "Sciences de l’Information et de la Communication (SIC)": "SIC",
    "Médecine et spécialités médicales": "MED",
    "Chirurgie et spécialités chirurgicales": "CHIR",
    "Santé de la mère et de l'enfant": "SME",
    "Santé de la mère et de l’enfant": "SME",
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
    "Mathématiques-Informatique, Physique Chimie (MPC)": "MPC",
    "Géographie": "GEOG",
    "Droit": "DRT",
    "Sociologie": "SOCIO",
    "Économie": "ECO",
    "Histoire": "HIST",
    "Philosophie": "PHILO",
}

ok, notfound = 0, 0
for filiere in Filiere.objects.all():
    nom = filiere.nom.strip()
    if nom in CODES:
        filiere.code = CODES[nom]
        filiere.save()
        print(f"✅ {nom} → {filiere.code}")
        ok += 1
    else:
        print(f"❌ {nom} → AUCUN CODE")
        notfound += 1

print(f"\nRésultat : {ok} mis à jour, {notfound} non trouvés")
