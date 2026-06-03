"""
Calcule et remplit l'empreinte SHA256 de tous les sujets qui n'en ont pas encore.
Usage : python manage.py shell < scripts/backfill_empreintes.py
"""
import hashlib
from django.core.files.base import ContentFile
from core.models import Sujet

a_jour = 0
erreurs = 0
ignores = 0

for sujet in Sujet.objects.filter(empreinte__isnull=True):
    try:
        fichier = sujet.fichier_pdf
        if not fichier or not fichier.name:
            ignores += 1
            print(f"⚠️  {sujet.id} — {sujet.titre} : pas de fichier")
            continue

        fichier.open("rb")
        empreinte = hashlib.sha256(fichier.read()).hexdigest()
        fichier.close()

        sujet.empreinte = empreinte
        sujet.save(update_fields=["empreinte"])
        print(f"✅ {sujet.id} — {sujet.titre[:40]} → empreinte calculée")
        a_jour += 1
    except Exception as e:
        erreurs += 1
        print(f"❌ {sujet.id} — {sujet.titre[:40]} : {e}")

print(f"\nRésultat : {a_jour} mis à jour, {ignores} ignorés, {erreurs} erreurs")
