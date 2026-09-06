from django.conf import settings
from django.db import transaction
from django.utils.timezone import now
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator
from apps.events.services import handle_review_confirmed
from apps.training.services import get_active_model
from apps.uploads.models import MediaAsset

from .models import Detection, RecognitionJob, ReviewAction
from .services import execute_job


def _owns_job(user, job):
    return user.is_superuser or job.media.batch.creator_id == user.id


def _detection_payload(detection):
    return {
        "id": detection.id,
        "sequence": detection.sequence,
        "bbox": {"x": detection.x, "y": detection.y, "width": detection.width, "height": detection.height},
        "original_class": detection.original_class,
        "effective_class": detection.effective_class,
        "confidence": detection.confidence,
        "reason": detection.reason,
        "model_class": detection.model_class,
        "model_class_label": detection.model_class,
        "review_status": detection.review_status,
        "is_demo_data": detection.is_demo_data,
    }


def _job_payload(job):
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "adapter": job.adapter,
        "model_version": job.model_version.version if job.model_version_id else None,
        "model_version_id": job.model_version_id,
        "is_demo_data": job.is_demo_data,
        "processed_frames": job.processed_frames,
        "total_frames": job.total_frames,
        "retry_count": job.retry_count,
        "error_message": job.error_message,
        "media": {
            "id": job.media_id,
            "kind": job.media.kind,
            "original_name": job.media.original_name,
            "url": job.media.original_file.url,
            "status": job.media.status,
        },
        "detections": [_detection_payload(item) for item in job.detections.all()],
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def create_job(request):
    media = MediaAsset.objects.select_related("batch").filter(id=request.data.get("media_id")).first()
    if media is None or (not request.user.is_superuser and media.batch.creator_id != request.user.id):
        return Response({"code": "media_not_found", "message": "媒体素材不存在"}, status=404)
    active_model = get_active_model()
    job, created = RecognitionJob.objects.get_or_create(
        media=media,
        defaults={
            "status": RecognitionJob.Status.QUEUED, "progress": 5, "total_frames": 1,
            "model_version": active_model, "adapter": active_model.model_type,
            "is_demo_data": active_model.model_type == "mock",
        },
    )
    if created:
        media.status = MediaAsset.Status.QUEUED
        media.save(update_fields=("status",))
        media.batch.status = "processing"
        media.batch.save(update_fields=("status", "updated_at"))
    return Response(_job_payload(job), status=201 if created else 200)


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def job_detail(request, job_id):
    job = RecognitionJob.objects.select_related("media__batch").prefetch_related("detections").filter(id=job_id).first()
    if job is None or not _owns_job(request.user, job):
        return Response({"code": "job_not_found", "message": "识别作业不存在"}, status=404)
    return Response(_job_payload(job))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def run_job(request, job_id):
    return _run_job_request(request, job_id)


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def run_mock(request, job_id):
    return _run_job_request(request, job_id, force_sync=True)


def _run_job_request(request, job_id, force_sync=False):
    job = RecognitionJob.objects.select_related("media__batch").filter(id=job_id).first()
    if job is None or not _owns_job(request.user, job):
        return Response({"code": "job_not_found", "message": "识别作业不存在"}, status=404)
    if settings.INFERENCE_ASYNC and not force_sync:
        from .tasks import run_inference

        try:
            run_inference.delay(job.id)
        except Exception as exc:
            job.status = RecognitionJob.Status.FAILED
            job.error_message = f"任务入队失败：{type(exc).__name__}"
            job.save(update_fields=("status", "error_message", "updated_at"))
            job.media.status = MediaAsset.Status.FAILED
            job.media.save(update_fields=("status",))
            return Response({"code": "queue_unavailable", "message": "识别服务暂不可用"}, status=503)
        return Response(_job_payload(job), status=202)
    try:
        job = execute_job(job.id)
    except Exception as exc:
        with transaction.atomic():
            failed = RecognitionJob.objects.select_for_update().get(id=job_id)
            failed.status = RecognitionJob.Status.FAILED
            failed.error_message = f"识别失败：{type(exc).__name__}"
            failed.save(update_fields=("status", "error_message", "updated_at"))
            failed.media.status = MediaAsset.Status.FAILED
            failed.media.save(update_fields=("status",))
        return Response({"code": "inference_failed", "message": "真实识别执行失败"}, status=500)
    job = RecognitionJob.objects.select_related("media").prefetch_related("detections").get(id=job.id)
    return Response(_job_payload(job))



@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def retry_job(request, job_id):
    job = RecognitionJob.objects.select_related("media__batch").filter(id=job_id).first()
    if job is None or not _owns_job(request.user, job):
        return Response({"code": "job_not_found", "message": "识别作业不存在"}, status=404)
    if job.status != RecognitionJob.Status.FAILED:
        return Response({"code": "job_not_failed", "message": "只有失败作业可以重试"}, status=409)
    job.status = RecognitionJob.Status.QUEUED
    job.progress = 5
    job.retry_count += 1
    job.error_message = ""
    job.save(update_fields=("status", "progress", "retry_count", "error_message", "updated_at"))
    job.media.status = MediaAsset.Status.QUEUED
    job.media.save(update_fields=("status",))
    return Response(_job_payload(job))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def review_detection(request, detection_id):
    detection = (
        Detection.objects.select_for_update()
        .select_related("job__media__batch")
        .filter(id=detection_id)
        .first()
    )
    if detection is None or not _owns_job(request.user, detection.job):
        return Response({"code": "detection_not_found", "message": "检测结果不存在"}, status=404)
    confirmed_class = request.data.get("confirmed_class", detection.original_class)
    valid_classes = {value for value, _ in Detection.DetectionClass.choices}
    if confirmed_class not in valid_classes:
        return Response({"code": "invalid_detection_class", "message": "检测类别不合法"}, status=400)
    previous_class = detection.effective_class
    detection.confirmed_class = confirmed_class
    detection.review_status = Detection.ReviewStatus.CONFIRMED
    detection.save(update_fields=("confirmed_class", "review_status"))
    ReviewAction.objects.create(
        detection=detection, operator=request.user, previous_class=previous_class,
        confirmed_class=confirmed_class, note=str(request.data.get("note", "")).strip(),
    )
    if not detection.job.detections.filter(review_status=Detection.ReviewStatus.PENDING).exists():
        detection.job.status = RecognitionJob.Status.COMPLETED
        detection.job.completed_at = now()
        detection.job.save(update_fields=("status", "completed_at", "updated_at"))
        detection.job.media.status = MediaAsset.Status.COMPLETED
        detection.job.media.save(update_fields=("status",))
    detection.refresh_from_db()
    # 复核确认后联动 Panel 状态与异常事件
    transaction.on_commit(lambda: handle_review_confirmed(detection, detection.job))
    return Response(_detection_payload(detection))
