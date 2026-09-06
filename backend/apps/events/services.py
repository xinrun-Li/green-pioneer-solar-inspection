from django.db import transaction
from django.utils.timezone import now

from apps.recognition.models import Detection, RecognitionJob
from apps.stations.models import Panel, PanelStatusHistory
from apps.inspections.models import InspectionRecord

from .models import AbnormalEvent


def _parse_panel_from_region_note(region_note: str):
    """从 region_note 解析区域和阵列名称，不凭视觉猜测。
    格式示例："北区 A2" → ("北区", "A2") 或 ("北区", None)
    """
    parts = region_note.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    if parts:
        return parts[0], None
    return None, None


@transaction.atomic
def handle_review_confirmed(detection: Detection, job: RecognitionJob):
    """Detection 复核确认后联动：更新 Panel 状态 + 创建/关闭异常事件。"""
    effective = detection.effective_class
    panel = _find_panel(job)
    if panel is None:
        return

    # 更新 Panel 当前状态
    old_status = panel.current_status
    status_map = {
        Detection.DetectionClass.NORMAL: Panel.Status.NORMAL,
        Detection.DetectionClass.CLEANING: Panel.Status.CLEANING,
        Detection.DetectionClass.REPAIR: Panel.Status.REPAIR,
    }
    new_status = status_map.get(effective)
    if new_status:
        panel.current_status = new_status
        panel.last_recognized_at = now()
        panel.save(update_fields=("current_status", "last_recognized_at"))

    # 记录状态变更历史
    if new_status and new_status != old_status:
        PanelStatusHistory.objects.create(
            panel=panel, status=new_status, reason=detection.reason or "",
            recorded_at=now(), source="recognition_review",
        )

    # 异常事件管理
    if effective in {Detection.DetectionClass.CLEANING, Detection.DetectionClass.REPAIR}:
        event_type = (
            AbnormalEvent.EventType.CLEANING
            if effective == Detection.DetectionClass.CLEANING
            else AbnormalEvent.EventType.REPAIR
        )
        # 检查是否已有同类型未关闭事件
        existing = AbnormalEvent.objects.filter(
            panel=panel, event_type=event_type, status=AbnormalEvent.Status.OPEN
        ).first()
        if existing is None:
            AbnormalEvent.objects.create(
                panel=panel,
                event_type=event_type,
                reason=detection.reason or f"AI 识别为{detection.get_effective_class_display()}",
                source_job=job,
            )
    elif effective == Detection.DetectionClass.NORMAL:
        # 正常→关闭所有未关闭的异常事件
        AbnormalEvent.objects.filter(
            panel=panel, status=AbnormalEvent.Status.OPEN
        ).update(
            status=AbnormalEvent.Status.CLOSED,
            closed_at=now(),
            closed_note="AI 识别正常，自动关闭",
        )

    review_action = detection.review_actions.select_related("operator").order_by("-created_at").first()
    InspectionRecord.objects.create(
        panel=panel,
        operator=review_action.operator if review_action else None,
        source=InspectionRecord.Source.REVIEW,
        status=new_status or Panel.Status.UNKNOWN,
        summary=f"人工复核识别结果：{detection.get_effective_class_display()}",
        details={
            "detection_id": detection.id,
            "job_id": job.id,
            "original_class": detection.original_class,
            "confirmed_class": detection.effective_class,
            "confidence": detection.confidence,
            "reason": detection.reason,
        },
    )


def _find_panel(job):
    """从 job 关联的 media batch region_note 中查找 Panel。"""
    region_note = job.media.batch.region_note
    region_name, array_code = _parse_panel_from_region_note(region_note)
    if not region_name:
        return None
    try:
        region = job.media.batch.station.regions.filter(name__icontains=region_name).first()
        if region is None:
            return None
        arrays = region.arrays.all()
        if array_code:
            arrays = [a for a in arrays if a.code == array_code]
        if not arrays:
            return None
        # 按元数据（region_note）关联到阵列，返回该阵列的第一个 Panel
        # 后续通过任务航点定位可精确到具体 Panel
        return arrays[0].panels.order_by("row", "column").first()
    except Exception:
        return None
