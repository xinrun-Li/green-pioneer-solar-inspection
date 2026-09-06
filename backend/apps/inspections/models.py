from django.conf import settings
from django.db import models


class InspectionTask(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        CONFIRMED = "confirmed", "已确认"
        RUNNING = "running", "执行中"
        PAUSED = "paused", "已暂停"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失败"
        CANCELLED = "cancelled", "已取消"

    title = models.CharField("任务标题", max_length=200)
    description = models.TextField("任务描述", blank=True)
    station = models.ForeignKey(
        "stations.Station", related_name="inspection_tasks",
        on_delete=models.PROTECT,
    )
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT)
    total_waypoints = models.PositiveIntegerField("总航点数", default=0)
    visited_waypoints = models.PositiveIntegerField("已巡检航点数", default=0)
    coverage = models.FloatField("覆盖率", default=0.0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="created_inspections",
        on_delete=models.PROTECT,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="confirmed_inspections",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "巡检任务"
        verbose_name_plural = "巡检任务"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class Waypoint(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待巡检"
        VISITED = "visited", "已巡检"
        SKIPPED = "skipped", "已跳过"
        FAILED = "failed", "失败"

    task = models.ForeignKey(InspectionTask, related_name="waypoints", on_delete=models.CASCADE)
    panel = models.ForeignKey("stations.Panel", related_name="inspection_waypoints", on_delete=models.PROTECT)
    row = models.PositiveSmallIntegerField("行")
    column = models.PositiveSmallIntegerField("列")
    order = models.PositiveIntegerField("序号")
    status = models.CharField("状态", max_length=12, choices=Status.choices, default=Status.PENDING)
    visited_at = models.DateTimeField("巡检时间", null=True, blank=True)
    uploaded_media = models.ForeignKey(
        "uploads.MediaAsset", related_name="waypoint_media",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    notes = models.CharField("备注", max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "航点"
        verbose_name_plural = "航点"
        ordering = ("task", "order")
        constraints = [
            models.UniqueConstraint(fields=("task", "panel"), name="uniq_waypoint_panel_per_task"),
            models.UniqueConstraint(fields=("task", "order"), name="uniq_waypoint_order_per_task"),
        ]

    def __str__(self):
        return f"{self.task.title} · 航点{self.order} ({self.panel.full_code})"


class InspectionEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "任务创建"
        CONFIRMED = "confirmed", "任务确认"
        STARTED = "started", "任务开始"
        PAUSED = "paused", "任务暂停"
        RESUMED = "resumed", "任务恢复"
        CANCELLED = "cancelled", "任务取消"
        FAILED = "failed", "任务失败"
        COMPLETED = "completed", "任务完成"
        WAYPOINT_VISITED = "waypoint_visited", "航点已巡检"
        WAYPOINT_SKIPPED = "waypoint_skipped", "航点已跳过"
        MEDIA_UPLOADED = "media_uploaded", "素材已上传"
        MEDIA_MISSING = "media_missing", "素材缺失"

    task = models.ForeignKey(InspectionTask, related_name="events", on_delete=models.CASCADE)
    event_type = models.CharField("事件类型", max_length=20, choices=EventType.choices)
    description = models.TextField("描述", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="inspection_events",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField("发生时间", auto_now_add=True)

    class Meta:
        verbose_name = "巡检事件"
        verbose_name_plural = "巡检事件"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.task.title} · {self.get_event_type_display()}"


class InspectionRecord(models.Model):
    """可追溯的巡检结果记录，覆盖任务巡检、手动检查和人工复核。"""

    class Source(models.TextChoices):
        TASK = "task", "巡检任务"
        MANUAL = "manual", "手动检查"
        REVIEW = "review", "人工复核"

    task = models.ForeignKey(
        InspectionTask, related_name="history_records", null=True, blank=True,
        on_delete=models.PROTECT,
    )
    panel = models.ForeignKey(
        "stations.Panel", related_name="inspection_records", null=True, blank=True,
        on_delete=models.PROTECT,
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="inspection_records", null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    source = models.CharField("记录来源", max_length=16, choices=Source.choices)
    status = models.CharField("检查结果", max_length=16, default="unknown")
    summary = models.TextField("检查摘要", blank=True)
    details = models.JSONField("详细信息", default=dict, blank=True)
    recorded_at = models.DateTimeField("记录时间", auto_now_add=True)

    class Meta:
        verbose_name = "巡检历史记录"
        verbose_name_plural = "巡检历史记录"
        ordering = ("-recorded_at",)

    def __str__(self):
        return f"{self.get_source_display()} · {self.recorded_at:%Y-%m-%d %H:%M:%S}"
