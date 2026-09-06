import hashlib
from pathlib import Path

from django.db import IntegrityError, transaction
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator

from .models import MediaAsset, UploadBatch

ALLOWED_MIME = {
    "image/jpeg": MediaAsset.Kind.IMAGE,
    "image/png": MediaAsset.Kind.IMAGE,
    "image/webp": MediaAsset.Kind.IMAGE,
    "video/mp4": MediaAsset.Kind.VIDEO,
    "video/quicktime": MediaAsset.Kind.VIDEO,
}
IMAGE_LIMIT = 20 * 1024 * 1024
VIDEO_LIMIT = 1024 * 1024 * 1024


def _matches_signature(upload, mime_type):
    header = upload.read(16)
    upload.seek(0)
    checks = {
        "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": lambda value: value.startswith(b"RIFF") and value[8:12] == b"WEBP",
        "video/mp4": lambda value: value[4:8] == b"ftyp",
        "video/quicktime": lambda value: value[4:8] == b"ftyp",
    }
    return checks[mime_type](header)


def _station_for_user(user):
    if user.is_superuser:
        from apps.stations.models import Station

        return Station.objects.filter(is_active=True).first()
    return user.operator_profile.station


def _media_payload(media):
    job = getattr(media, "recognition_job", None)
    return {
        "id": media.id,
        "kind": media.kind,
        "original_name": media.original_name,
        "mime_type": media.mime_type,
        "size_bytes": media.size_bytes,
        "status": media.status,
        "url": media.original_file.url,
        "job_id": job.id if job else None,
    }


def _batch_payload(batch):
    return {
        "id": batch.id,
        "region_note": batch.region_note,
        "status": batch.status,
        "created_at": batch.created_at,
        "media": [_media_payload(media) for media in batch.media_assets.all()],
    }


@api_view(["GET", "POST"])
@permission_classes([IsApprovedOperator])
def batch_collection(request):
    if request.method == "GET":
        batches = UploadBatch.objects.filter(creator=request.user).prefetch_related("media_assets__recognition_job")[:12]
        return Response({"results": [_batch_payload(batch) for batch in batches]})

    station = _station_for_user(request.user)
    if station is None:
        return Response({"code": "station_not_assigned", "message": "当前账户尚未分配电站"}, status=409)
    batch = UploadBatch.objects.create(
        creator=request.user, station=station, region_note=str(request.data.get("region_note", "")).strip()
    )
    return Response(_batch_payload(batch), status=201)


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@parser_classes([MultiPartParser])
def upload_media(request, batch_id):
    batch = UploadBatch.objects.filter(id=batch_id, creator=request.user).first()
    if batch is None:
        return Response({"code": "batch_not_found", "message": "上传批次不存在"}, status=404)
    files = request.FILES.getlist("files")
    if not files:
        return Response({"code": "files_required", "message": "请选择至少一个图片或视频文件"}, status=400)
    if len(files) > 31:
        return Response({"code": "too_many_files", "message": "单批次最多上传 30 张图片和 1 个视频"}, status=400)

    validated = []
    existing_video = batch.media_assets.filter(kind=MediaAsset.Kind.VIDEO).exists()
    existing_images = batch.media_assets.filter(kind=MediaAsset.Kind.IMAGE).count()
    image_count = existing_images
    video_count = int(existing_video)
    for upload in files:
        kind = ALLOWED_MIME.get(upload.content_type)
        if kind is None:
            return Response({"code": "unsupported_media", "message": f"不支持文件类型：{Path(upload.name).name}"}, status=400)
        if not _matches_signature(upload, upload.content_type):
            return Response(
                {"code": "invalid_media_content", "message": f"文件内容与声明类型不一致：{Path(upload.name).name}"},
                status=400,
            )
        limit = VIDEO_LIMIT if kind == MediaAsset.Kind.VIDEO else IMAGE_LIMIT
        if upload.size > limit:
            label = "视频" if kind == MediaAsset.Kind.VIDEO else "图片"
            return Response({"code": "file_too_large", "message": f"{label}文件超过大小限制"}, status=400)
        if kind == MediaAsset.Kind.VIDEO:
            video_count += 1
        else:
            image_count += 1
        validated.append((upload, kind))
    if video_count > 1:
        return Response({"code": "too_many_videos", "message": "每个批次最多上传一个视频"}, status=400)
    if image_count > 30:
        return Response({"code": "too_many_images", "message": "每个批次最多上传 30 张图片"}, status=400)

    assets = []
    batch_checksums = set()
    try:
        with transaction.atomic():
            for upload, kind in validated:
                digest = hashlib.sha256()
                for chunk in upload.chunks():
                    digest.update(chunk)
                upload.seek(0)
                checksum = digest.hexdigest()
                if checksum in batch_checksums or MediaAsset.objects.filter(batch=batch, checksum=checksum).exists():
                    raise ValueError("duplicate_media")
                batch_checksums.add(checksum)
                assets.append(MediaAsset.objects.create(
                    batch=batch, kind=kind, original_file=upload,
                    original_name=Path(upload.name).name, mime_type=upload.content_type,
                    size_bytes=upload.size, checksum=checksum,
                ))
    except ValueError as exc:
        if str(exc) == "duplicate_media":
            return Response({"code": "duplicate_media", "message": "同一批次不能重复上传相同文件"}, status=409)
        raise
    except IntegrityError:
        return Response({"code": "too_many_videos", "message": "每个批次最多上传一个视频"}, status=400)
    return Response({"media": [_media_payload(asset) for asset in assets]}, status=201)
