from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models


def media_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"uploads/{instance.batch_id}/{uuid4().hex}{suffix}"


class UploadBatch(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "已创建"
        PROCESSING = "processing", "处理中"
        COMPLETED = "completed", "已完成"
        PARTIAL_FAILED = "partial_failed", "部分失败"

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="upload_batches", on_delete=models.PROTECT)
    station = models.ForeignKey("stations.Station", related_name="upload_batches", on_delete=models.PROTECT)
    region_note = models.TextField("区域备注", blank=True)
    status = models.CharField("批次状态", max_length=20, choices=Status.choices, default=Status.CREATED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "上传批次"
        verbose_name_plural = "上传批次"
        ordering = ("-created_at",)

    def __str__(self):
        return f"批次 #{self.pk} · {self.creator}"


class MediaAsset(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "图片"
        VIDEO = "video", "视频"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "已上传"
        QUEUED = "queued", "排队中"
        PROCESSING = "processing", "识别中"
        REVIEW = "review", "待复核"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失败"

    batch = models.ForeignKey(UploadBatch, related_name="media_assets", on_delete=models.PROTECT)
    kind = models.CharField("素材类型", max_length=12, choices=Kind.choices)
    original_file = models.FileField("原始文件", upload_to=media_upload_path, max_length=500)
    original_name = models.CharField("原文件名", max_length=255)
    mime_type = models.CharField("MIME 类型", max_length=100)
    size_bytes = models.PositiveBigIntegerField("文件大小")
    checksum = models.CharField("SHA-256", max_length=64)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.UPLOADED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "媒体素材"
        verbose_name_plural = "媒体素材"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("batch",), condition=models.Q(kind="video"), name="uniq_video_per_upload_batch"
            )
        ]

    def __str__(self):
        return self.original_name
