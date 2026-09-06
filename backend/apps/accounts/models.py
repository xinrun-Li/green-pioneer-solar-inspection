from django.conf import settings
from django.db import models


class ControlOperator(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "管理员"
        REVIEWER = "reviewer", "审核员"
        INSPECTOR = "inspector", "巡检员"
        VIEWER = "viewer", "查看员"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已拒绝"
        DISABLED = "disabled", "已停用"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="operator_profile")
    display_name = models.CharField("姓名", max_length=80)
    phone = models.CharField("手机号", max_length=32, blank=True)
    role = models.CharField("业务角色", max_length=16, choices=Role.choices, default=Role.INSPECTOR)
    review_status = models.CharField("审核状态", max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    rejection_reason = models.TextField("驳回原因", blank=True)
    station = models.ForeignKey(
        "stations.Station", verbose_name="所属电站", related_name="operators", null=True, blank=True, on_delete=models.PROTECT
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="审核人", related_name="reviewed_operators",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    created_at = models.DateTimeField("注册时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "控制人员"
        verbose_name_plural = "控制人员"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.display_name}（{self.user.username}）"

    @property
    def can_access_frontend(self):
        """前台访问由账号是否有效决定，审核状态仅供后台管理展示。"""
        return self.user.is_active

    @property
    def has_account_management_permission(self):
        return self.user.is_superuser or self.user.is_staff or self.role in {
            self.Role.ADMIN,
            self.Role.REVIEWER,
        }


class AuditLog(models.Model):
    class ActionType(models.TextChoices):
        APPROVE = "approve", "审核通过"
        REJECT = "reject", "驳回申请"
        ROLE_CHANGE = "role_change", "角色变更"
        DISABLE = "disable", "停用账号"
        DELETE = "delete", "删除账号"
        RESET_PASSWORD = "reset_password", "重置密码"
        MODEL_SWITCH = "model_switch", "模型切换"
        CREATE = "create", "创建账号"
        EDIT = "edit", "编辑账号"

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="操作者", related_name="account_audit_logs",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    action_type = models.CharField("操作类型", max_length=32, choices=ActionType.choices)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="目标用户", related_name="targeted_account_audit_logs",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    reason = models.TextField("操作原因", blank=True)
    created_at = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        verbose_name = "账号操作日志"
        verbose_name_plural = "账号操作日志"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_action_type_display()} · {self.target_user or '目标账号已删除'}"


class AccountNotification(models.Model):
    class Kind(models.TextChoices):
        APPROVED = "approved", "审核通过"
        REJECTED = "rejected", "审核驳回"
        STATUS = "status", "账号状态"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="接收用户", related_name="account_notifications",
        on_delete=models.CASCADE,
    )
    kind = models.CharField("通知类型", max_length=16, choices=Kind.choices)
    title = models.CharField("通知标题", max_length=120)
    content = models.TextField("通知内容")
    is_read = models.BooleanField("已读", default=False)
    created_at = models.DateTimeField("通知时间", auto_now_add=True)

    class Meta:
        verbose_name = "账号通知"
        verbose_name_plural = "账号通知"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} · {self.user.username}"
