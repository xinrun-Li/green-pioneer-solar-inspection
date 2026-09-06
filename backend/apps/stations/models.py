from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Station(models.Model):
    code = models.CharField("电站代码", max_length=32, unique=True)
    name = models.CharField("电站名称", max_length=120)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "电站"
        verbose_name_plural = "电站"
        ordering = ("code",)

    def __str__(self):
        return self.name


class Region(models.Model):
    class Direction(models.TextChoices):
        EAST = "east", "东区"
        SOUTH = "south", "南区"
        WEST = "west", "西区"
        NORTH = "north", "北区"

    station = models.ForeignKey(Station, related_name="regions", on_delete=models.PROTECT)
    name = models.CharField("区域名称", max_length=40)
    direction = models.CharField("方向", max_length=12, choices=Direction.choices)
    sort_order = models.PositiveSmallIntegerField("排序", default=0)

    class Meta:
        verbose_name = "区域"
        verbose_name_plural = "区域"
        ordering = ("sort_order", "id")
        constraints = [models.UniqueConstraint(fields=("station", "name"), name="uniq_region_name_per_station")]

    def __str__(self):
        return f"{self.station.name} · {self.name}"


class SolarArray(models.Model):
    region = models.ForeignKey(Region, related_name="arrays", on_delete=models.PROTECT)
    code = models.CharField("阵列编号", max_length=16)
    rows = models.PositiveSmallIntegerField("行数", default=4, validators=[MinValueValidator(1), MaxValueValidator(20)])
    columns = models.PositiveSmallIntegerField("列数", default=5, validators=[MinValueValidator(1), MaxValueValidator(20)])
    sort_order = models.PositiveSmallIntegerField("排序", default=0)

    class Meta:
        verbose_name = "光伏阵列"
        verbose_name_plural = "光伏阵列"
        ordering = ("sort_order", "id")
        constraints = [models.UniqueConstraint(fields=("region", "code"), name="uniq_array_code_per_region")]

    def __str__(self):
        return f"{self.region.name} · {self.code}"


class Panel(models.Model):
    class Status(models.TextChoices):
        NORMAL = "normal", "正常"
        CLEANING = "cleaning", "需要清洗"
        REPAIR = "repair", "需要维修"
        PROCESSING = "processing", "识别中"
        UNKNOWN = "unknown", "未知"

    array = models.ForeignKey(SolarArray, related_name="panels", on_delete=models.PROTECT)
    full_code = models.CharField("完整编号", max_length=40)
    short_code = models.CharField("短编号", max_length=24)
    row = models.PositiveSmallIntegerField("行", validators=[MinValueValidator(1)])
    column = models.PositiveSmallIntegerField("列", validators=[MinValueValidator(1)])
    current_status = models.CharField("当前状态", max_length=16, choices=Status.choices, default=Status.UNKNOWN)
    last_recognized_at = models.DateTimeField("最近识别时间", null=True, blank=True)

    class Meta:
        verbose_name = "光伏组件"
        verbose_name_plural = "光伏组件"
        ordering = ("array_id", "row", "column")
        constraints = [
            models.UniqueConstraint(fields=("array", "row", "column"), name="uniq_panel_position_per_array"),
            models.UniqueConstraint(fields=("array", "full_code"), name="uniq_panel_code_per_array"),
        ]

    def __str__(self):
        return f"{self.array.region.name} · {self.full_code}"


class PanelStatusHistory(models.Model):
    panel = models.ForeignKey(Panel, related_name="status_history", on_delete=models.PROTECT)
    status = models.CharField("状态", max_length=16, choices=Panel.Status.choices)
    reason = models.CharField("原因", max_length=120, blank=True)
    recorded_at = models.DateTimeField("记录时间")
    source = models.CharField("来源", max_length=32, default="demo_seed")

    class Meta:
        verbose_name = "组件状态历史"
        verbose_name_plural = "组件状态历史"
        ordering = ("-recorded_at",)
        constraints = [models.UniqueConstraint(fields=("panel", "recorded_at"), name="uniq_panel_history_time")]

    def __str__(self):
        return f"{self.panel.full_code} · {self.get_status_display()}"

