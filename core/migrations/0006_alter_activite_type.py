from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_pushsubscription"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activite",
            name="type",
            field=models.CharField(
                choices=[
                    ("telechargement", "Téléchargement"),
                    ("consultation", "Consultation"),
                    ("publication", "Publication"),
                    ("profil_modifie", "Profil modifié"),
                    ("validation", "Validation admin"),
                    ("archivage", "Archivage admin"),
                ],
                max_length=20,
            ),
        ),
    ]
