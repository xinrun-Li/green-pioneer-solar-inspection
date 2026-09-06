from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("training", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelversion",
            name="model_sha256",
            field=models.CharField(blank=True, max_length=64, verbose_name="模型 SHA-256"),
        ),
    ]
