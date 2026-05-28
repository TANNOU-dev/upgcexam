from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_alter_activite_type"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="filiere",
            options={
                "ordering": ["ordre"],
                "verbose_name": "Filière",
                "verbose_name_plural": "Filières",
            },
        ),
        migrations.AddField(
            model_name="filiere",
            name="ordre",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
    ]
