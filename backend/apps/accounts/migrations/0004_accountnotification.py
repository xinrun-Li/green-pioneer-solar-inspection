from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_auditlog_operator_nullable"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("approved", "审核通过"), ("rejected", "审核驳回"), ("status", "账号状态")], max_length=16, verbose_name="通知类型")),
                ("title", models.CharField(max_length=120, verbose_name="通知标题")),
                ("content", models.TextField(verbose_name="通知内容")),
                ("is_read", models.BooleanField(default=False, verbose_name="已读")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="通知时间")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="account_notifications", to=settings.AUTH_USER_MODEL, verbose_name="接收用户")),
            ],
            options={
                "verbose_name": "账号通知",
                "verbose_name_plural": "账号通知",
                "ordering": ("-created_at",),
            },
        ),
    ]
