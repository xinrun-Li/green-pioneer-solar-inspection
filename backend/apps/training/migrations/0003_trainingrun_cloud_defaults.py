from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0002_modelversion_model_sha256"),
    ]

    operations = [
        migrations.AlterField(
            model_name="trainingrun",
            name="batch_size",
            field=models.PositiveIntegerField(default=16, verbose_name="批大小"),
        ),
        migrations.AlterField(
            model_name="trainingrun",
            name="device",
            field=models.CharField(default="cuda", max_length=32, verbose_name="训练设备"),
        ),
        migrations.AlterField(
            model_name="trainingrun",
            name="image_size",
            field=models.PositiveIntegerField(default=1024, verbose_name="图像尺寸"),
        ),
    ]
