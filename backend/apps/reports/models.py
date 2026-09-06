from django.conf import settings
from django.db import models


class Report(models.Model):
    class ReportType(models.TextChoices):
        WEB = "web", "网页报告"
        EXCEL = "excel", "Excel 报告"
        PDF = "pdf", "PDF 报告"

    class Status(models.TextChoices):
        GENERATING = "generating", "生成中"
        READY = "ready", "已就绪"
        FAILED = "failed", "失败"

    report_type = models.CharField("报告类型", max_length=10, choices=ReportType.choices)
    status = models.CharField("状态", max_length=10, choices=Status.choices, default=Status.GENERATING)
    parameters = models.JSONField("生成参数", blank=True, default=dict)
    filters = models.JSONField("筛选条件", blank=True, default=dict)
    snapshot_data = models.JSONField("快照数据", blank=True, default=dict)
    file = models.FileField("导出文件", upload_to="reports/", blank=True, max_length=500)
    error_message = models.TextField("错误信息", blank=True)
    progress = models.IntegerField("生成进度", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="创建人"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "报告"
        verbose_name_plural = "报告"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.created_at}"