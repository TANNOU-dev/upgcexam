from django.db import migrations, models


def migrer_archive_vers_en_attente(apps, schema_editor):
    Sujet = apps.get_model("core", "Sujet")
    Sujet.objects.filter(statut="archive").update(statut="en_attente")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_verification_alter_filiere_code_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sujet",
            name="statut",
            field=models.CharField(
                choices=[
                    ("actif", "Actif"),
                    ("en_attente", "En attente de validation"),
                    ("archive", "Archivé"),
                ],
                default="actif",
                max_length=12,
            ),
        ),
        migrations.RunPython(migrer_archive_vers_en_attente, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="verification",
            name="email",
            field=models.EmailField(db_index=True, max_length=254),
        ),
        migrations.AlterField(
            model_name="verification",
            name="expire_le",
            field=models.DateTimeField(db_index=True),
        ),
    ]
