from django.conf import settings
from django.db import models


class AgentConversation(models.Model):
    """智能助手对话"""

    class Source(models.TextChoices):
        LOCAL = "local", "本地规则引擎"
        CLOUD = "cloud", "云端 API"

    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        DRAFTED = "drafted", "已生成草稿"
        CONFIRMED = "confirmed", "已确认执行"
        REJECTED = "rejected", "已拒绝"
        FAILED = "failed", "执行失败"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="agent_conversations",
        on_delete=models.CASCADE,
    )
    message = models.TextField("用户消息")
    intent = models.CharField("意图类型", max_length=64, blank=True)
    slots = models.JSONField("槽位参数", default=dict, blank=True)
    response = models.TextField("助手回复", blank=True)
    draft_action = models.JSONField("草稿动作", default=dict, blank=True, null=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    source = models.CharField("来源", max_length=16, choices=Source.choices, default=Source.LOCAL)
    confidence = models.FloatField("置信度", default=0.0)
    error_message = models.TextField("错误信息", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "助手对话"
        verbose_name_plural = "助手对话"
        ordering = ("-created_at",)

    def __str__(self):
        return f"[{self.get_intent_display()}] {self.message[:40]}"


class AgentAction(models.Model):
    """助手执行动作审计"""

    class ActionType(models.TextChoices):
        QUERY = "query", "查询"
        CREATE = "create", "创建"
        UPDATE = "update", "更新"
        DELETE = "delete", "删除"
        EXPORT = "export", "导出"
        NAVIGATE = "navigate", "导航跳转"

    class Result(models.TextChoices):
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"
        PENDING = "pending", "待执行"

    conversation = models.ForeignKey(
        AgentConversation, related_name="actions",
        on_delete=models.CASCADE,
    )
    action_type = models.CharField("动作类型", max_length=16, choices=ActionType.choices)
    target = models.CharField("目标对象", max_length=64, blank=True)
    payload = models.JSONField("动作参数", default=dict, blank=True)
    result = models.CharField("结果", max_length=16, choices=Result.choices, default=Result.PENDING)
    result_data = models.JSONField("结果数据", default=dict, blank=True, null=True)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="agent_actions",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "助手动作"
        verbose_name_plural = "助手动作"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_action_type_display()} → {self.target}"