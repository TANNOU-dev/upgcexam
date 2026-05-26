from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_presencesession"),
    ]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("endpoint", models.URLField(max_length=500)),
                ("auth", models.CharField(max_length=100)),
                ("p256dh", models.CharField(max_length=100)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                (
                    "utilisateur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_subscriptions",
                        to="auth.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Abonnement Push",
                "verbose_name_plural": "Abonnements Push",
            },
        ),
    ]
