from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recognition", "0003_recognitionjob_model_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="detection",
            name="model_class",
            field=models.CharField(blank=True, max_length=32, verbose_name="模型原始类别"),
        ),
    ]
