from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def dataset_asset_upload_path(instance, filename):
    return f"datasets/assets/{uuid4().hex}{Path(filename).suffix.lower()}"


class DatasetAsset(models.Model):
    class AnnotationStatus(models.TextChoices):
        PENDING = "pending", "待标注"
        ANNOTATING = "annotating", "标注中"
        ANNOTATED = "annotated", "已标注"
        REJECTED = "rejected", "已弃用"

    class SourceType(models.TextChoices):
        UPLOADED = "uploaded", "手动上传"
        LOW_CONFIDENCE = "low_confidence", "低置信度"
        MANUAL_CORRECTION = "manual_correction", "人工修正"
        MANUAL_UNRECOGNIZED = "manual_unrecognized", "人工标记无法识别"
        INFERENCE_FAILED = "inference_failed", "识别失败"

    file = models.FileField("样本文件", upload_to=dataset_asset_upload_path, max_length=500)
    source_media = models.ForeignKey(
        "uploads.MediaAsset", related_name="dataset_assets", null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name="来源媒体",
    )
    original_name = models.CharField("原文件名", max_length=255)
    media_type = models.CharField("媒体类型", max_length=20)
    checksum = models.CharField("SHA-256", max_length=64)
    size_bytes = models.PositiveBigIntegerField("文件大小", default=0)
    width = models.PositiveIntegerField("宽度", default=0)
    height = models.PositiveIntegerField("高度", default=0)
    annotation_status = models.CharField(
        "标注状态", max_length=16, choices=AnnotationStatus.choices, default=AnnotationStatus.PENDING
    )
    source_type = models.CharField("来源类型", max_length=24, choices=SourceType.choices, default=SourceType.UPLOADED)
    is_hard_sample = models.BooleanField("困难样本", default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="dataset_assets", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "数据集样本"
        verbose_name_plural = "数据集样本"
        constraints = [models.UniqueConstraint(fields=("created_by", "checksum"), name="uniq_dataset_asset_owner_checksum")]

    def __str__(self):
        return self.original_name


class Annotation(models.Model):
    class ClassName(models.TextChoices):
        NORMAL = "normal", "正常"
        CLEANING = "cleaning", "需要清洗"
        REPAIR = "repair", "需要维修"

    class Source(models.TextChoices):
        AUTO = "auto", "模型生成"
        MANUAL = "manual", "人工标注"
        CORRECTED = "corrected", "人工修正"

    asset = models.ForeignKey(DatasetAsset, related_name="annotations", on_delete=models.CASCADE)
    class_name = models.CharField("类别", max_length=16, choices=ClassName.choices)
    x = models.FloatField("左上 X", validators=[MinValueValidator(0), MaxValueValidator(1)])
    y = models.FloatField("左上 Y", validators=[MinValueValidator(0), MaxValueValidator(1)])
    width = models.FloatField("宽度", validators=[MinValueValidator(0), MaxValueValidator(1)])
    height = models.FloatField("高度", validators=[MinValueValidator(0), MaxValueValidator(1)])
    source = models.CharField("标注来源", max_length=16, choices=Source.choices, default=Source.MANUAL)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="dataset_annotations", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "数据集标注"
        verbose_name_plural = "数据集标注"

    def __str__(self):
        return f"{self.asset} · {self.get_class_name_display()}"


class DatasetVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        FROZEN = "frozen", "已冻结"
        ARCHIVED = "archived", "已归档"

    name = models.CharField("名称", max_length=120)
    version = models.CharField("版本号", max_length=40)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT)
    assets = models.ManyToManyField(DatasetAsset, related_name="dataset_versions", blank=True)
    train_count = models.PositiveIntegerField("训练样本数", default=0)
    validation_count = models.PositiveIntegerField("验证样本数", default=0)
    test_count = models.PositiveIntegerField("测试样本数", default=0)
    class_config = models.JSONField("类别配置", default=list)
    export_path = models.CharField("导出路径", max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="dataset_versions", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("created_by", "version"), name="uniq_dataset_version_owner_version")]
        verbose_name = "数据集版本"
        verbose_name_plural = "数据集版本"

    def __str__(self):
        return f"{self.name} · {self.version}"
