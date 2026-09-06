from django.conf import settings
from django.db import models


class AbnormalEvent(models.Model):
    class EventType(models.TextChoices):
        CLEANING = "cleaning", "需要清洗"
        REPAIR = "repair", "需要维修"

    class Status(models.TextChoices):
        OPEN = "open", "未处理"
        CLOSED = "closed", "已关闭"

    panel = models.ForeignKey("stations.Panel", related_name="abnormal_events", on_delete=models.PROTECT)
    event_type = models.CharField("事件类型", max_length=16, choices=EventType.choices)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField("开启时间", auto_now_add=True)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    reason = models.TextField("异常原因", blank=True)
    source_job = models.ForeignKey(
        "recognition.RecognitionJob", related_name="source_events",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="closed_events",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    closed_note = models.CharField("关闭备注", max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "异常事件"
        verbose_name_plural = "异常事件"
        ordering = ("-opened_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("panel", "event_type", "status"),
                condition=models.Q(status="open"),
                name="uniq_open_event_per_panel_type",
            )
        ]

    def __str__(self):
        return f"{self.panel.full_code} · {self.get_event_type_display()} · {self.get_status_display()}"