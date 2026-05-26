from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_professional_fixes"),
    ]

    operations = [
        migrations.CreateModel(
            name="PresenceSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("debut", models.DateTimeField(auto_now_add=True)),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("secondes", models.PositiveIntegerField(default=0)),
                (
                    "utilisateur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="presences",
                        to="auth.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Session de présence",
                "verbose_name_plural": "Sessions de présence",
                "ordering": ["-debut"],
            },
        ),
    ]
