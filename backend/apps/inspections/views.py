from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator
from apps.events.models import AbnormalEvent
from apps.stations.models import Panel, PanelStatusHistory

from .models import InspectionEvent, InspectionRecord, InspectionTask, Waypoint
from .serializers import (
    InspectionEventSerializer,
    InspectionRecordSerializer,
    InspectionTaskCreateSerializer,
    InspectionTaskDetailSerializer,
    InspectionTaskListSerializer,
    WaypointSerializer,
)
from .services import generate_s_route, simulate_execute


def _task_payload(task):
    serializer = InspectionTaskDetailSerializer(task)
    return serializer.data


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def task_list(request):
    tasks = InspectionTask.objects.select_related("station", "created_by", "created_by__operator_profile").order_by("-created_at")
    if not request.user.is_superuser:
        station_id = getattr(getattr(request.user, "operator_profile", None), "station_id", None)
        tasks = tasks.filter(created_by=request.user) if station_id is None else tasks.filter(station_id=station_id)
    status = request.query_params.get("status")
    if status:
        tasks = tasks.filter(status=status)
    station_id = request.query_params.get("station_id")
    if station_id:
        tasks = tasks.filter(station_id=station_id)
    return Response({
        "count": tasks.count(),
        "results": [InspectionTaskListSerializer(t).data for t in tasks],
    })


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def history_list(request):
    """返回巡检任务、手动检查和人工复核的统一历史记录。"""
    records = InspectionRecord.objects.select_related(
        "task", "panel__array__region", "operator", "operator__operator_profile",
    )
    if not request.user.is_superuser:
        station_id = getattr(getattr(request.user, "operator_profile", None), "station_id", None)
        if station_id is None:
            records = records.none()
        else:
            records = records.filter(Q(task__station_id=station_id) | Q(panel__array__region__station_id=station_id))

    for name, lookup in (("date_from", "recorded_at__date__gte"), ("date_to", "recorded_at__date__lte")):
        value = request.query_params.get(name)
        if value:
            try:
                records = records.filter(**{lookup: date.fromisoformat(value)})
            except ValueError:
                return Response({"code": "invalid_date", "message": f"{name} 日期格式应为 YYYY-MM-DD"}, status=400)

    source = request.query_params.get("source")
    if source:
        valid_sources = {value for value, _ in InspectionRecord.Source.choices}
        if source not in valid_sources:
            return Response({"code": "invalid_source", "message": "历史记录来源不合法"}, status=400)
        records = records.filter(source=source)
    status = request.query_params.get("status")
    if status:
        records = records.filter(status=status)

    total = records.count()
    source_counts = {
        key: records.filter(source=key).count()
        for key, _ in InspectionRecord.Source.choices
    }
    status_counts = {
        key: records.filter(status=key).count()
        for key, _ in Panel.Status.choices
    }
    abnormal_events = AbnormalEvent.objects.all()
    if not request.user.is_superuser:
        station_id = getattr(getattr(request.user, "operator_profile", None), "station_id", None)
        abnormal_events = abnormal_events.filter(panel__array__region__station_id=station_id) if station_id else abnormal_events.none()
    abnormal_events = abnormal_events.filter(
        opened_at__date__gte=request.query_params["date_from"]
    ) if request.query_params.get("date_from") else abnormal_events
    abnormal_events = abnormal_events.filter(
        opened_at__date__lte=request.query_params["date_to"]
    ) if request.query_params.get("date_to") else abnormal_events
    results = records[:200]
    return Response({
        "count": total,
        "stats": {
            "total_records": total,
            "task_records": source_counts[InspectionRecord.Source.TASK],
            "manual_records": source_counts[InspectionRecord.Source.MANUAL],
            "review_records": source_counts[InspectionRecord.Source.REVIEW],
            "classification_counts": {
                "normal": status_counts.get(Panel.Status.NORMAL, 0),
                "needs_cleaning": status_counts.get(Panel.Status.CLEANING, 0),
                "needs_repair": status_counts.get(Panel.Status.REPAIR, 0),
            },
            "abnormal_events": {
                "open": abnormal_events.filter(status=AbnormalEvent.Status.OPEN).count(),
                "closed": abnormal_events.filter(status=AbnormalEvent.Status.CLOSED).count(),
            },
        },
        "results": InspectionRecordSerializer(results, many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def manual_check(request):
    """记录一次人工检查，并同步组件当前状态与状态变更历史。"""
    panel_id = request.data.get("panel_id")
    status = str(request.data.get("status", Panel.Status.UNKNOWN)).strip()
    note = str(request.data.get("note", "")).strip()[:120]
    valid_statuses = {Panel.Status.NORMAL, Panel.Status.CLEANING, Panel.Status.REPAIR, Panel.Status.UNKNOWN}
    if status not in valid_statuses:
        return Response({"code": "invalid_status", "message": "手动检查状态不合法"}, status=400)

    panels = Panel.objects.select_related("array__region__station")
    if not request.user.is_superuser:
        station_id = getattr(getattr(request.user, "operator_profile", None), "station_id", None)
        panels = panels.filter(array__region__station_id=station_id) if station_id else panels.none()
    panel = panels.filter(id=panel_id).first()
    if panel is None:
        return Response({"code": "panel_not_found", "message": "组件不存在或不属于当前电站"}, status=404)

    recorded_at = now()
    previous_status = panel.current_status
    panel.current_status = status
    panel.last_recognized_at = recorded_at
    panel.save(update_fields=("current_status", "last_recognized_at"))
    PanelStatusHistory.objects.create(
        panel=panel, status=status, reason=note, recorded_at=recorded_at, source="manual_check",
    )
    record = InspectionRecord.objects.create(
        panel=panel,
        operator=request.user,
        source=InspectionRecord.Source.MANUAL,
        status=status,
        summary=f"手动检查：{dict(Panel.Status.choices).get(status, status)}",
        details={"previous_status": previous_status, "note": note},
    )
    return Response({"record": InspectionRecordSerializer(record).data, "message": "手动检查已记录"})


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def task_detail(request, task_id):
    task = InspectionTask.objects.select_related(
        "station", "created_by", "created_by__operator_profile", "confirmed_by", "confirmed_by__operator_profile",
    ).prefetch_related("waypoints__panel__array__region", "events").filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    return Response(_task_payload(task))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def create_task(request):
    serializer = InspectionTaskCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"code": "invalid_input", "message": "输入校验失败", "errors": serializer.errors}, status=400)
    task = InspectionTask.objects.create(
        title=serializer.validated_data["title"],
        description=serializer.validated_data.get("description", ""),
        station=serializer.validated_data["station"],
        created_by=request.user,
    )
    # 生成 S 形路线
    generate_s_route(task)
    InspectionEvent.objects.create(
        task=task, event_type=InspectionEvent.EventType.CREATED,
        description=f"任务创建，共 {task.total_waypoints} 个航点",
        created_by=request.user,
    )
    return Response(_task_payload(task), status=201)


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def confirm_task(request, task_id):
    task = InspectionTask.objects.filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    if task.status != InspectionTask.Status.DRAFT:
        return Response({"code": "invalid_status", "message": f"当前状态 {task.get_status_display()} 不允许确认"}, status=409)
    task.status = InspectionTask.Status.CONFIRMED
    task.confirmed_by = request.user
    task.confirmed_at = now()
    task.save(update_fields=("status", "confirmed_by", "confirmed_at", "updated_at"))
    InspectionEvent.objects.create(
        task=task, event_type=InspectionEvent.EventType.CONFIRMED,
        description=f"任务已确认，等待开始执行",
        created_by=request.user,
    )
    return Response(_task_payload(task))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def start_task(request, task_id):
    task = InspectionTask.objects.filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    if task.status != InspectionTask.Status.CONFIRMED:
        return Response({"code": "invalid_status", "message": f"当前状态 {task.get_status_display()} 不允许开始"}, status=409)
    task.status = InspectionTask.Status.RUNNING
    task.started_at = now()
    task.save(update_fields=("status", "started_at", "updated_at"))
    InspectionEvent.objects.create(
        task=task, event_type=InspectionEvent.EventType.STARTED,
        description="任务开始执行",
        created_by=request.user,
    )
    return Response(_task_payload(task))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def pause_task(request, task_id):
    task = InspectionTask.objects.filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    if task.status != InspectionTask.Status.RUNNING:
        return Response({"code": "invalid_status", "message": f"当前状态 {task.get_status_display()} 不允许暂停"}, status=409)
    task.status = InspectionTask.Status.PAUSED
    task.save(update_fields=("status", "updated_at"))
    InspectionEvent.objects.create(
        task=task, event_type=InspectionEvent.EventType.PAUSED,
        description="任务已暂停",
        created_by=request.user,
    )
    return Response(_task_payload(task))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def resume_task(request, task_id):
    task = InspectionTask.objects.filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    if task.status != InspectionTask.Status.PAUSED:
        return Response({"code": "invalid_status", "message": f"当前状态 {task.get_status_display()} 不允许恢复"}, status=409)
    task.status = InspectionTask.Status.RUNNING
    task.save(update_fields=("status", "updated_at"))
    InspectionEvent.objects.create(
        task=task, event_type=InspectionEvent.EventType.RESUMED,
        description="任务恢复执行",
        created_by=request.user,
    )
    return Response(_task_payload(task))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def cancel_task(request, task_id):
    task = InspectionTask.objects.filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    if task.status in (InspectionTask.Status.COMPLETED, InspectionTask.Status.CANCELLED):
        return Response({"code": "invalid_status", "message": f"当前状态 {task.get_status_display()} 不允许取消"}, status=409)
    task.status = InspectionTask.Status.CANCELLED
    task.save(update_fields=("status", "updated_at"))
    InspectionEvent.objects.create(
        task=task, event_type=InspectionEvent.EventType.CANCELLED,
        description="任务已取消",
        created_by=request.user,
    )
    return Response(_task_payload(task))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def simulate_execute_view(request, task_id):
    """模拟执行：自动载入预置素材，标记航点，更新进度"""
    task = InspectionTask.objects.select_related("station").prefetch_related("waypoints").filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    if task.status != InspectionTask.Status.RUNNING:
        return Response({"code": "invalid_status", "message": f"当前状态 {task.get_status_display()} 不允许执行"}, status=409)
    skipped = simulate_execute(task)
    if skipped:
        return Response({
            "code": "media_missing",
            "message": f"缺少 {skipped} 个航点的预置素材，已跳过，可通过补传续跑",
            "data": _task_payload(task),
        }, status=200)
    return Response(_task_payload(task))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def skip_waypoint(request, task_id, waypoint_id):
    task = InspectionTask.objects.filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    waypoint = task.waypoints.filter(id=waypoint_id).first()
    if waypoint is None:
        return Response({"code": "waypoint_not_found", "message": "航点不存在"}, status=404)
    if waypoint.status != Waypoint.Status.PENDING:
        return Response({"code": "invalid_status", "message": "航点当前状态不允许跳过"}, status=409)
    waypoint.status = Waypoint.Status.SKIPPED
    waypoint.notes = request.data.get("reason", "人工跳过")
    waypoint.save(update_fields=("status", "notes"))
    InspectionEvent.objects.create(
        task=task, event_type=InspectionEvent.EventType.WAYPOINT_SKIPPED,
        description=f"航点 {waypoint.order} ({waypoint.panel.full_code}) 已跳过: {waypoint.notes}",
        created_by=request.user,
    )
    return Response(_task_payload(task))


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def task_events(request, task_id):
    task = InspectionTask.objects.filter(id=task_id).first()
    if task is None:
        return Response({"code": "task_not_found", "message": "巡检任务不存在"}, status=404)
    events = task.events.select_related("created_by").order_by("-created_at")
    return Response({
        "count": events.count(),
        "results": [InspectionEventSerializer(e).data for e in events],
    })
