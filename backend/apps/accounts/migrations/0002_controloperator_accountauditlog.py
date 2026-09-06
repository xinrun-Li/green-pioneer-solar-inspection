from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="controloperator",
            name="phone",
            field=models.CharField(blank=True, max_length=32, verbose_name="手机号"),
        ),
        migrations.AddField(
            model_name="controloperator",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "管理员"),
                    ("reviewer", "审核员"),
                    ("inspector", "巡检员"),
                    ("viewer", "查看员"),
                ],
                default="inspector",
                max_length=16,
                verbose_name="业务角色",
            ),
        ),
        migrations.AddField(
            model_name="controloperator",
            name="rejection_reason",
            field=models.TextField(blank=True, verbose_name="驳回原因"),
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("approve", "审核通过"),
                            ("reject", "驳回申请"),
                            ("role_change", "角色变更"),
                            ("disable", "停用账号"),
                            ("delete", "删除账号"),
                            ("reset_password", "重置密码"),
                            ("create", "创建账号"),
                            ("edit", "编辑账号"),
                        ],
                        max_length=32,
                        verbose_name="操作类型",
                    ),
                ),
                ("reason", models.TextField(blank=True, verbose_name="操作原因")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="操作时间")),
                (
                    "operator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="account_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="操作者",
                    ),
                ),
                (
                    "target_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="targeted_account_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="目标用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "账号操作日志",
                "verbose_name_plural": "账号操作日志",
                "ordering": ("-created_at",),
            },
        ),
    ]
