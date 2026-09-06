import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inspections", "0001_initial"),
        ("stations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InspectionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("task", "巡检任务"), ("manual", "手动检查"), ("review", "人工复核")], max_length=16, verbose_name="记录来源")),
                ("status", models.CharField(default="unknown", max_length=16, verbose_name="检查结果")),
                ("summary", models.TextField(blank=True, verbose_name="检查摘要")),
                ("details", models.JSONField(blank=True, default=dict, verbose_name="详细信息")),
                ("recorded_at", models.DateTimeField(auto_now_add=True, verbose_name="记录时间")),
                ("operator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inspection_records", to=settings.AUTH_USER_MODEL)),
                ("panel", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inspection_records", to="stations.panel")),
                ("task", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="history_records", to="inspections.inspectiontask")),
            ],
            options={
                "verbose_name": "巡检历史记录",
                "verbose_name_plural": "巡检历史记录",
                "ordering": ("-recorded_at",),
            },
        ),
    ]
