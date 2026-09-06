from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator
from apps.events.models import AbnormalEvent

from .models import Panel, PanelStatusHistory, Station


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def current_station_map(request):
    if request.user.is_superuser:
        station = Station.objects.filter(is_active=True).first()
    else:
        station = request.user.operator_profile.station
    if station is None:
        return Response({"code": "station_not_assigned", "message": "当前账户尚未分配电站"}, status=409)

    regions = station.regions.prefetch_related("arrays__panels")
    counts = dict(
        Panel.objects.filter(array__region__station=station)
        .values_list("current_status")
        .annotate(total=Count("id"))
    )
    payload = {
        "id": station.id,
        "code": station.code,
        "name": station.name,
        "summary": {status: counts.get(status, 0) for status, _ in Panel.Status.choices},
        "panel_count": sum(counts.values()),
        "regions": [],
    }
    for region in regions:
        region_data = {"id": region.id, "name": region.name, "direction": region.direction, "arrays": []}
        for array in region.arrays.all():
            region_data["arrays"].append({
                "id": array.id,
                "code": array.code,
                "rows": array.rows,
                "columns": array.columns,
                "panels": [
                    {
                        "id": panel.id, "full_code": panel.full_code, "short_code": panel.short_code,
                        "row": panel.row, "column": panel.column, "status": panel.current_status,
                        "last_recognized_at": panel.last_recognized_at,
                    }
                    for panel in array.panels.all()
                ],
            })
        payload["regions"].append(region_data)
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def panel_detail(request, panel_id):
    panel = Panel.objects.select_related("array__region__station").filter(id=panel_id).first()
    if panel is None:
        return Response({"code": "panel_not_found", "message": "组件不存在"}, status=404)
    status_history = PanelStatusHistory.objects.filter(panel=panel).order_by("-recorded_at")[:20]
    events = AbnormalEvent.objects.filter(panel=panel).order_by("-opened_at")[:10]
    return Response({
        "id": panel.id,
        "full_code": panel.full_code,
        "short_code": panel.short_code,
        "row": panel.row,
        "column": panel.column,
        "status": panel.current_status,
        "last_recognized_at": panel.last_recognized_at,
        "array_code": panel.array.code,
        "region_name": panel.array.region.name,
        "station_name": panel.array.region.station.name,
        "status_history": [
            {
                "id": h.id, "status": h.status, "reason": h.reason or "",
                "recorded_at": h.recorded_at, "source": h.source,
            }
            for h in status_history
        ],
        "events": [
            {
                "id": e.id, "event_type": e.event_type, "status": e.status,
                "reason": e.reason or "", "opened_at": e.opened_at,
                "closed_at": e.closed_at, "closed_note": e.closed_note or "",
            }
            for e in events
        ],
    })

