from django.db import transaction
from django.utils.timezone import now
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator

from .models import AbnormalEvent
from .serializers import AbnormalEventSerializer


def _event_payload(event):
    serializer = AbnormalEventSerializer(event)
    return serializer.data


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def event_list(request):
    events = AbnormalEvent.objects.select_related("panel__array__region").order_by("-opened_at")
    # 过滤
    panel_id = request.query_params.get("panel_id")
    if panel_id:
        events = events.filter(panel_id=panel_id)
    status = request.query_params.get("status")
    if status:
        events = events.filter(status=status)
    event_type = request.query_params.get("event_type")
    if event_type:
        events = events.filter(event_type=event_type)
    return Response({
        "count": events.count(),
        "results": [AbnormalEventSerializer(e).data for e in events],
    })


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def event_detail(request, event_id):
    event = AbnormalEvent.objects.select_related("panel__array__region", "closed_by").filter(id=event_id).first()
    if event is None:
        return Response({"code": "event_not_found", "message": "异常事件不存在"}, status=404)
    return Response(_event_payload(event))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def close_event(request, event_id):
    event = AbnormalEvent.objects.select_related("panel").filter(id=event_id).first()
    if event is None:
        return Response({"code": "event_not_found", "message": "异常事件不存在"}, status=404)
    if event.status == AbnormalEvent.Status.CLOSED:
        return Response({"code": "event_already_closed", "message": "事件已关闭"}, status=409)
    event.status = AbnormalEvent.Status.CLOSED
    event.closed_at = now()
    event.closed_by = request.user
    event.closed_note = request.data.get("note", "")
    event.save(update_fields=("status", "closed_at", "closed_by", "closed_note", "updated_at"))
    return Response(_event_payload(event))


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def panel_events(request, panel_id):
    events = AbnormalEvent.objects.filter(panel_id=panel_id).select_related("panel").order_by("-opened_at")
    return Response({
        "count": events.count(),
        "results": [AbnormalEventSerializer(e).data for e in events],
    })