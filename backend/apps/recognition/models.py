from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class RecognitionJob(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "已创建"
        QUEUED = "queued", "已排队"
        RUNNING = "running", "运行中"
        REVIEW = "review", "待复核"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失败"

    media = models.OneToOneField("uploads.MediaAsset", related_name="recognition_job", on_delete=models.PROTECT)
    model_version = models.ForeignKey(
        "training.ModelVersion",
        related_name="recognition_jobs",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name="模型版本",
    )
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.CREATED)
    progress = models.PositiveSmallIntegerField("进度", default=0, validators=[MaxValueValidator(100)])
    adapter = models.CharField("推理适配器", max_length=32, default="mock")
    is_demo_data = models.BooleanField("演示数据", default=True)
    processed_frames = models.PositiveIntegerField("已处理帧数", default=0)
    total_frames = models.PositiveIntegerField("总帧数", default=1)
    retry_count = models.PositiveSmallIntegerField("重试次数", default=0)
    error_message = models.TextField("错误信息", blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "识别作业"
        verbose_name_plural = "识别作业"
        ordering = ("-created_at",)

    def __str__(self):
        return f"作业 #{self.pk} · {self.media}"


class Detection(models.Model):
    class DetectionClass(models.TextChoices):
        NORMAL = "normal", "正常"
        CLEANING = "cleaning", "需要清洗"
        REPAIR = "repair", "需要维修"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "待复核"
        CONFIRMED = "confirmed", "已确认"

    job = models.ForeignKey(RecognitionJob, related_name="detections", on_delete=models.PROTECT)
    sequence = models.PositiveIntegerField("结果序号")
    model_class = models.CharField("模型原始类别", max_length=32, blank=True)
    x = models.FloatField("左上 X", validators=[MinValueValidator(0), MaxValueValidator(1)])
    y = models.FloatField("左上 Y", validators=[MinValueValidator(0), MaxValueValidator(1)])
    width = models.FloatField("宽度", validators=[MinValueValidator(0), MaxValueValidator(1)])
    height = models.FloatField("高度", validators=[MinValueValidator(0), MaxValueValidator(1)])
    original_class = models.CharField("原始类别", max_length=16, choices=DetectionClass.choices)
    confirmed_class = models.CharField("确认类别", max_length=16, choices=DetectionClass.choices, blank=True)
    confidence = models.FloatField("置信度", validators=[MinValueValidator(0), MaxValueValidator(1)])
    reason = models.CharField("辅助原因", max_length=160, blank=True)
    review_status = models.CharField(
        "复核状态", max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.CONFIRMED
    )
    is_demo_data = models.BooleanField("演示数据", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "检测结果"
        verbose_name_plural = "检测结果"
        ordering = ("sequence",)
        constraints = [models.UniqueConstraint(fields=("job", "sequence"), name="uniq_detection_sequence")]

    def __str__(self):
        return f"作业 #{self.job_id} · 结果 {self.sequence}"

    @property
    def effective_class(self):
        return self.confirmed_class or self.original_class


class ReviewAction(models.Model):
    detection = models.ForeignKey(Detection, related_name="review_actions", on_delete=models.PROTECT)
    operator = models.ForeignKey("auth.User", related_name="detection_reviews", on_delete=models.PROTECT)
    previous_class = models.CharField("修改前类别", max_length=16, choices=Detection.DetectionClass.choices)
    confirmed_class = models.CharField("确认类别", max_length=16, choices=Detection.DetectionClass.choices)
    note = models.CharField("复核备注", max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "复核记录"
        verbose_name_plural = "复核记录"
        ordering = ("-created_at",)

    def __str__(self):
        return f"结果 #{self.detection_id} · {self.get_confirmed_class_display()}"
