from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="datasetasset",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("uploaded", "手动上传"),
                    ("low_confidence", "低置信度"),
                    ("manual_correction", "人工修正"),
                    ("manual_unrecognized", "人工标记无法识别"),
                    ("inference_failed", "识别失败"),
                ],
                default="uploaded",
                max_length=24,
                verbose_name="来源类型",
            ),
        ),
    ]
