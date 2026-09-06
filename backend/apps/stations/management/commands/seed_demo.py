import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.stations.models import Panel, PanelStatusHistory, Region, SolarArray, Station


class Command(BaseCommand):
    help = "幂等初始化演示电站、4 区、12 阵列、240 组件和 30 天历史数据"

    @transaction.atomic
    def handle(self, *args, **options):
        station, _ = Station.objects.update_or_create(
            code="DEMO-001", defaults={"name": "绿能先锋示范光伏电站", "is_active": True}
        )
        region_specs = [
            ("东区", Region.Direction.EAST), ("南区", Region.Direction.SOUTH),
            ("西区", Region.Direction.WEST), ("北区", Region.Direction.NORTH),
        ]
        panels = []
        for region_index, (name, direction) in enumerate(region_specs, start=1):
            region, _ = Region.objects.update_or_create(
                station=station, name=name, defaults={"direction": direction, "sort_order": region_index}
            )
            for array_index in range(1, 4):
                array, _ = SolarArray.objects.update_or_create(
                    region=region, code=f"A{array_index}",
                    defaults={"rows": 4, "columns": 5, "sort_order": array_index},
                )
                for row in range(1, 5):
                    for column in range(1, 6):
                        sequence = (row - 1) * 5 + column
                        panel, _ = Panel.objects.update_or_create(
                            array=array, row=row, column=column,
                            defaults={
                                "full_code": f"A{array_index}-R{row:02d}-C{column:02d}",
                                "short_code": f"A{array_index}-{sequence:03d}",
                            },
                        )
                        panels.append(panel)

        self._seed_history(panels)
        self.stdout.write(self.style.SUCCESS(
            f"演示数据就绪：{Station.objects.count()} 个电站，{station.regions.count()} 个区域，"
            f"{SolarArray.objects.filter(region__station=station).count()} 个阵列，{len(panels)} 块组件，"
            f"{PanelStatusHistory.objects.filter(panel__array__region__station=station).count()} 条历史记录"
        ))

    def _seed_history(self, panels):
        randomizer = random.Random(20260805)
        today = timezone.localdate()
        start = today - timedelta(days=29)
        histories = []
        reasons = {Panel.Status.CLEANING: "积灰趋势", Panel.Status.REPAIR: "可见异常，建议复检", Panel.Status.NORMAL: ""}

        existing = set(PanelStatusHistory.objects.filter(panel__in=panels).values_list("panel_id", "recorded_at"))
        latest = {}
        for day_offset in range(30):
            day = start + timedelta(days=day_offset)
            recorded_at = timezone.make_aware(datetime.combine(day, time(hour=10)))
            for panel in panels:
                roll = randomizer.random()
                status = Panel.Status.REPAIR if roll < 0.035 else Panel.Status.CLEANING if roll < 0.14 else Panel.Status.NORMAL
                latest[panel.id] = (status, recorded_at)
                if (panel.id, recorded_at) not in existing:
                    histories.append(PanelStatusHistory(
                        panel=panel, status=status, reason=reasons[status], recorded_at=recorded_at, source="demo_seed"
                    ))
        PanelStatusHistory.objects.bulk_create(histories, batch_size=1000)
        for panel in panels:
            panel.current_status, panel.last_recognized_at = latest[panel.id]
        Panel.objects.bulk_update(panels, ("current_status", "last_recognized_at"), batch_size=500)

