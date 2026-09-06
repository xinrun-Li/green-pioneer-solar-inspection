from django.conf import settings
from django.db import models


class ModelVersion(models.Model):
    class ModelType(models.TextChoices):
        MOCK = "mock", "模拟模型"
        YOLO = "yolo", "YOLO"

    class Status(models.TextChoices):
        CANDIDATE = "candidate", "候选"
        ACTIVE = "active", "启用"
        RETIRED = "retired", "已退役"
        FAILED = "failed", "失败"

    name = models.CharField("名称", max_length=120)
    version = models.CharField("版本号", max_length=40, unique=True)
    model_type = models.CharField("模型类型", max_length=16, choices=ModelType.choices)
    model_path = models.CharField("模型路径", max_length=500, blank=True)
    model_sha256 = models.CharField("模型 SHA-256", max_length=64, blank=True)
    dataset_version = models.ForeignKey(
        "datasets.DatasetVersion", related_name="model_versions", null=True, blank=True,
        on_delete=models.PROTECT, verbose_name="数据集版本",
    )
    metrics = models.JSONField("指标", default=dict, blank=True)
    class_config = models.JSONField("类别配置", default=list)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.CANDIDATE)
    is_active = models.BooleanField("当前启用", default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="model_versions", on_delete=models.PROTECT)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="activated_model_versions", null=True, blank=True, on_delete=models.PROTECT
    )
    activated_at = models.DateTimeField("启用时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "模型版本"
        verbose_name_plural = "模型版本"

    def __str__(self):
        return f"{self.name} · {self.version}"


class TrainingRun(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "已创建"
        QUEUED = "queued", "已排队"
        RUNNING = "running", "训练中"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失败"
        CANCELLED = "cancelled", "已取消"

    dataset_version = models.ForeignKey("datasets.DatasetVersion", related_name="training_runs", on_delete=models.PROTECT)
    base_model_version = models.ForeignKey(
        ModelVersion, related_name="derived_training_runs", null=True, blank=True, on_delete=models.PROTECT
    )
    output_model_version = models.OneToOneField(
        ModelVersion, related_name="source_training_run", null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.CREATED)
    epochs = models.PositiveIntegerField("训练轮数", default=50)
    image_size = models.PositiveIntegerField("图像尺寸", default=1024)
    batch_size = models.PositiveIntegerField("批大小", default=16)
    device = models.CharField("训练设备", max_length=32, default="cuda")
    progress = models.PositiveSmallIntegerField("进度", default=0)
    metrics = models.JSONField("指标", default=dict, blank=True)
    log_file = models.CharField("日志路径", max_length=500, blank=True)
    error_message = models.TextField("错误信息", blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="training_runs", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "训练任务"
        verbose_name_plural = "训练任务"

    def __str__(self):
        return f"训练任务 #{self.pk} · {self.dataset_version}"
