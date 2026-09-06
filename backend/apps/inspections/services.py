"""巡检任务服务层：S形路线生成、模拟执行"""
import os
import random
from datetime import timedelta

from django.conf import settings
from django.utils.timezone import now

from apps.stations.models import Panel, SolarArray

from .models import InspectionEvent, InspectionRecord, InspectionTask, Waypoint


def generate_s_route(task: InspectionTask) -> None:
    """为任务生成 S 形路线（蛇形遍历）航点。

    按阵列排序，每个阵列内按 S 形遍历：奇数行从左到右，偶数行从右到左。
    """
    arrays = SolarArray.objects.filter(region__station=task.station).order_by("region__sort_order", "sort_order")
    panels = Panel.objects.filter(array__in=arrays).select_related("array").order_by("array_id", "row", "column")
    # 按 (array_id, row, column) 排序后，按 array 分组再 S 形排列
    from collections import defaultdict
    array_groups = defaultdict(list)
    for p in panels:
        array_groups[p.array_id].append(p)

    waypoints = []
    order = 0
    for array in arrays:
        group = array_groups.get(array.id, [])
        # 按行分组
        rows = defaultdict(list)
        for p in group:
            rows[p.row].append(p)
        sorted_rows = sorted(rows.items())
        for row_idx, (row_num, row_panels) in enumerate(sorted_rows):
            # 按列排序
            row_panels.sort(key=lambda x: x.column)
            if row_idx % 2 == 1:
                # 偶数行（0-based索引为奇数）从右到左
                row_panels.reverse()
            for p in row_panels:
                order += 1
                waypoints.append(Waypoint(
                    task=task, panel=p, row=p.row, column=p.column,
                    order=order,
                ))
    Waypoint.objects.bulk_create(waypoints, batch_size=500)
    task.total_waypoints = order
    task.save(update_fields=("total_waypoints", "updated_at"))


def simulate_execute(task: InspectionTask) -> int:
    """模拟执行任务：自动载入预置素材，标记航点，更新进度。

    返回因缺少素材而跳过的航点数量（需要补传后通过续跑重试）。
    """
    waypoints = list(task.waypoints.filter(status=Waypoint.Status.PENDING).order_by("order"))
    if not waypoints:
        return 0

    # 检测预置素材目录
    preset_dir = os.path.join(settings.MEDIA_ROOT, "presets", f"station_{task.station_id}")
    preset_files = {}
    if os.path.isdir(preset_dir):
        for fname in os.listdir(preset_dir):
            panel_code = fname.split("_")[0] if "_" in fname else fname.rsplit(".", 1)[0]
            preset_files[panel_code] = fname

    skipped_count = 0
    visited_count = 0
    base_time = now()

    for i, wp in enumerate(waypoints):
        panel_code = wp.panel.short_code
        if panel_code in preset_files:
            wp.status = Waypoint.Status.VISITED
            wp.visited_at = base_time + timedelta(seconds=(i + 1) * 2)
            wp.notes = "模拟执行"
            visited_count += 1
            wp.save(update_fields=("status", "visited_at", "notes"))
            InspectionEvent.objects.create(
                task=task, event_type=InspectionEvent.EventType.WAYPOINT_VISITED,
                description=f"航点 {wp.order} ({wp.panel.full_code}) 已巡检",
            )
        else:
            wp.status = Waypoint.Status.SKIPPED
            wp.notes = "预置素材缺失"
            skipped_count += 1
            wp.save(update_fields=("status", "notes"))
            InspectionEvent.objects.create(
                task=task, event_type=InspectionEvent.EventType.MEDIA_MISSING,
                description=f"航点 {wp.order} ({wp.panel.full_code}) 缺少预置素材，已跳过",
            )

    task.visited_waypoints = Waypoint.objects.filter(task=task, status=Waypoint.Status.VISITED).count()
    task.total_waypoints = task.waypoints.count()
    task.coverage = round(task.visited_waypoints / task.total_waypoints * 100, 1) if task.total_waypoints > 0 else 0.0

    all_visited = task.visited_waypoints == task.total_waypoints
    if all_visited:
        task.status = InspectionTask.Status.COMPLETED
        task.completed_at = now()
        InspectionEvent.objects.create(
            task=task, event_type=InspectionEvent.EventType.COMPLETED,
            description=f"巡检完成，覆盖率 {task.coverage}%",
        )
    else:
        task.status = InspectionTask.Status.PAUSED
        InspectionEvent.objects.create(
            task=task, event_type=InspectionEvent.EventType.PAUSED,
            description=f"存在 {skipped_count} 个跳过航点，等待补传后续跑",
        )
    InspectionRecord.objects.create(
        task=task,
        operator=task.created_by,
        source=InspectionRecord.Source.TASK,
        summary=(
            f"巡检任务完成，覆盖率 {task.coverage}%"
            if all_visited else f"巡检执行完成，覆盖率 {task.coverage}%，跳过 {skipped_count} 个航点"
        ),
        details={
            "total_waypoints": task.total_waypoints,
            "visited_waypoints": task.visited_waypoints,
            "skipped_waypoints": skipped_count,
            "coverage": task.coverage,
            "execution_status": task.status,
        },
    )
    task.save(update_fields=("status", "visited_waypoints", "total_waypoints", "coverage", "completed_at", "updated_at"))
    return skipped_count
