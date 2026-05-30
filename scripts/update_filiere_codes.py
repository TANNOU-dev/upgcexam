"""
Mise à jour des codes filières avec les abréviations validées.
Usage : python manage.py shell < scripts/update_filiere_codes.py
"""
import re
from core.models import Filiere

CODES = {
    "IGA Agriculture": "AGRI",
    "IGA Économie et Gestion Agropastorale": "GAP",
    "IGA Zootechnie": "ZOO",
    "UFR-LA Lettres Modernes": "LM",
    "UFR-LA Anglais": "ANG",
    "UFR-LA Sciences de l'Information et de la Communication": "SIC",
    "UFR-MD Médecine et spécialités médicales": "MED",
    "UFR-MD Chirurgie et spécialités chirurgicales": "CHIR",
    "UFR-MD Santé de la mère et de l'enfant": "SME",
    "UFR-MD Sciences fondamentales et biologiques": "SFB",
    "UFR-MD Santé publique et spécialités connexes": "SP",
    "UFR-SB Géosciences": "GEO",
    "UFR-SB Biochimie-Génétique": "BG",
    "UFR-SB Biologie Végétale": "BV",
    "UFR-SB Biologie Animale": "BA",
    "UFR-SB Mathématiques": "MATH",
    "UFR-SB Physique Chimie": "PC",
    "UFR-SB Informatique": "INFO",
    "UFR-SB Mathématiques-Informatique, Physique Chimie": "MPC",
    "UFR-SS Géographie": "GEOG",
    "UFR-SS Droit": "DRT",
    "UFR-SS Sociologie": "SOCIO",
    "UFR-SS Économie": "ECO",
    "UFR-SS Histoire": "HIST",
    "UFR-SS Philosophie": "PHILO",
}

for filiere in Filiere.objects.all():
    # Cherche une correspondance exacte ou partielle
    nom_strip = filiere.nom.strip()
    if nom_strip in CODES:
        code = CODES[nom_strip]
        filiere.code = code
        filiere.save()
        print(f"✅ {nom_strip} → {code}")
    else:
        # Cherche par mot-clé
        trouve = False
        for key, code in CODES.items():
            mots = re.split(r'[\s,]+', key.lower())
            if all(m in nom_strip.lower() for m in mots if len(m) > 3):
                filiere.code = code
                filiere.save()
                print(f"⚠️ {nom_strip} → {code} (correspondance partielle: {key})")
                trouve = True
                break
        if not trouve:
            print(f"❌ {nom_strip} → AUCUN CODE TROUVÉ")
