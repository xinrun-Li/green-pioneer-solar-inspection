from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_accountnotification"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("approve", "审核通过"),
                    ("reject", "驳回申请"),
                    ("role_change", "角色变更"),
                    ("disable", "停用账号"),
                    ("delete", "删除账号"),
                    ("reset_password", "重置密码"),
                    ("model_switch", "模型切换"),
                    ("create", "创建账号"),
                    ("edit", "编辑账号"),
                ],
                max_length=32,
                verbose_name="操作类型",
            ),
        ),
    ]
