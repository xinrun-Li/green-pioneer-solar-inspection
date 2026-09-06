import hashlib
import json
from pathlib import Path

from django.db import transaction
from django.db.models import Q
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator

from .models import Annotation, DatasetAsset, DatasetVersion

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"}
CLASSES = {value for value, _ in Annotation.ClassName.choices}


def _owned_asset(user, asset_id):
    query = DatasetAsset.objects.filter(id=asset_id)
    return query.first() if user.is_superuser else query.filter(created_by=user).first()


def _annotation_payload(item):
    return {
        "id": item.id, "asset_id": item.asset_id, "class_name": item.class_name,
        "bbox": {"x": item.x, "y": item.y, "width": item.width, "height": item.height},
        "source": item.source, "operator": item.operator_id,
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


def _asset_payload(asset):
    return {
        "id": asset.id, "original_name": asset.original_name, "media_type": asset.media_type,
        "size_bytes": asset.size_bytes, "width": asset.width, "height": asset.height,
        "annotation_status": asset.annotation_status, "source_type": asset.source_type,
        "is_hard_sample": asset.is_hard_sample, "url": asset.file.url,
        "annotations": [_annotation_payload(item) for item in asset.annotations.select_related("operator")],
        "created_at": asset.created_at,
    }


def _version_payload(version):
    return {
        "id": version.id, "name": version.name, "version": version.version, "status": version.status,
        "asset_ids": list(version.assets.values_list("id", flat=True)),
        "train_count": version.train_count, "validation_count": version.validation_count,
        "test_count": version.test_count, "class_config": version.class_config,
        "export_path": version.export_path, "created_at": version.created_at,
    }


@api_view(["GET", "POST"])
@permission_classes([IsApprovedOperator])
@parser_classes([MultiPartParser, JSONParser])
def asset_collection(request):
    if request.method == "GET":
        assets = DatasetAsset.objects.filter(created_by=request.user).prefetch_related("annotations")
        status_filter = request.query_params.get("status")
        source_filter = request.query_params.get("source")
        search = request.query_params.get("search", "").strip()
        if status_filter:
            assets = assets.filter(annotation_status=status_filter)
        if source_filter:
            assets = assets.filter(source_type=source_filter)
        if search:
            assets = assets.filter(Q(original_name__icontains=search))
        assets = assets.order_by("created_at", "id")
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
            limit = min(100, max(1, int(request.query_params.get("limit", 24))))
        except (TypeError, ValueError):
            offset, limit = 0, 24
        total = assets.count()
        page = list(assets[offset:offset + limit])
        next_offset = offset + len(page) if offset + len(page) < total else None
        return Response({
            "count": total,
            "next_offset": next_offset,
            "results": [_asset_payload(asset) for asset in page],
        })
    upload = request.FILES.get("file")
    if upload is None:
        return Response({"code": "file_required", "message": "请上传样本文件"}, status=400)
    if upload.content_type not in ALLOWED_TYPES:
        return Response({"code": "unsupported_media", "message": "仅支持 JPG、PNG、WEBP、MP4 和 MOV"}, status=400)
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    checksum = digest.hexdigest()
    if DatasetAsset.objects.filter(created_by=request.user, checksum=checksum).exists():
        return Response({"code": "duplicate_asset", "message": "该样本已经上传过"}, status=409)
    source_type = str(request.data.get("source_type", DatasetAsset.SourceType.UPLOADED))
    if source_type not in DatasetAsset.SourceType.values:
        source_type = DatasetAsset.SourceType.UPLOADED
    asset = DatasetAsset.objects.create(
        file=upload, original_name=Path(upload.name).name, media_type=upload.content_type,
        checksum=checksum, size_bytes=upload.size, created_by=request.user,
        source_type=source_type,
        is_hard_sample=str(request.data.get("is_hard_sample", "false")).lower() == "true",
    )
    return Response(_asset_payload(asset), status=201)


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def asset_detail(request, asset_id):
    asset = _owned_asset(request.user, asset_id)
    if asset is None:
        return Response({"code": "asset_not_found", "message": "数据集样本不存在"}, status=404)
    return Response(_asset_payload(asset))


def _bbox(data):
    try:
        values = {key: float(data[key]) for key in ("x", "y", "width", "height")}
    except (KeyError, TypeError, ValueError):
        return None
    if any(value < 0 or value > 1 for value in values.values()):
        return None
    return values


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def create_annotation(request, asset_id):
    asset = _owned_asset(request.user, asset_id)
    if asset is None:
        return Response({"code": "asset_not_found", "message": "数据集样本不存在"}, status=404)
    class_name = request.data.get("class_name")
    bbox = _bbox(request.data.get("bbox", request.data))
    source = request.data.get("source", Annotation.Source.MANUAL)
    if class_name not in CLASSES or bbox is None or source not in Annotation.Source.values:
        return Response({"code": "invalid_annotation", "message": "类别、标注来源或边界框不合法"}, status=400)
    annotation = Annotation.objects.create(
        asset=asset, class_name=class_name, **bbox, source=source, operator=request.user,
    )
    asset.annotation_status = DatasetAsset.AnnotationStatus.ANNOTATED
    asset.save(update_fields=("annotation_status", "updated_at"))
    return Response(_annotation_payload(annotation), status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsApprovedOperator])
def annotation_detail(request, annotation_id):
    annotation = Annotation.objects.select_related("asset").filter(id=annotation_id).first()
    if annotation is None or (not request.user.is_superuser and annotation.asset.created_by_id != request.user.id):
        return Response({"code": "annotation_not_found", "message": "标注不存在"}, status=404)
    if request.method == "DELETE":
        asset = annotation.asset
        annotation.delete()
        if not asset.annotations.exists():
            asset.annotation_status = DatasetAsset.AnnotationStatus.PENDING
            asset.save(update_fields=("annotation_status", "updated_at"))
        return Response(status=204)
    class_name = request.data.get("class_name", annotation.class_name)
    bbox = _bbox(request.data.get("bbox", request.data))
    if class_name not in CLASSES or bbox is None:
        return Response({"code": "invalid_annotation", "message": "类别或边界框不合法"}, status=400)
    for key, value in bbox.items():
        setattr(annotation, key, value)
    annotation.class_name = class_name
    annotation.source = Annotation.Source.CORRECTED
    annotation.operator = request.user
    annotation.save(update_fields=("class_name", "x", "y", "width", "height", "source", "operator", "updated_at"))
    return Response(_annotation_payload(annotation))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def submit_asset(request, asset_id):
    asset = _owned_asset(request.user, asset_id)
    if asset is None:
        return Response({"code": "asset_not_found", "message": "数据集样本不存在"}, status=404)
    if not asset.annotations.exists():
        return Response({"code": "annotations_required", "message": "至少添加一个标注后才能提交"}, status=409)
    asset.annotation_status = DatasetAsset.AnnotationStatus.ANNOTATED
    asset.save(update_fields=("annotation_status", "updated_at"))
    return Response(_asset_payload(asset))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def reject_asset(request, asset_id):
    asset = _owned_asset(request.user, asset_id)
    if asset is None:
        return Response({"code": "asset_not_found", "message": "数据集样本不存在"}, status=404)
    asset.annotation_status = DatasetAsset.AnnotationStatus.REJECTED
    asset.save(update_fields=("annotation_status", "updated_at"))
    return Response(_asset_payload(asset))


@api_view(["GET", "POST"])
@permission_classes([IsApprovedOperator])
def version_collection(request):
    if request.method == "GET":
        versions = DatasetVersion.objects.filter(created_by=request.user).prefetch_related("assets")
        return Response({"results": [_version_payload(item) for item in versions]})
    asset_ids = request.data.get("asset_ids")
    if isinstance(asset_ids, str):
        try:
            asset_ids = json.loads(asset_ids)
        except json.JSONDecodeError:
            asset_ids = []
    if asset_ids is None:
        assets = list(DatasetAsset.objects.filter(
            created_by=request.user, annotation_status=DatasetAsset.AnnotationStatus.ANNOTATED,
        ))
        asset_ids = [asset.id for asset in assets]
    elif not isinstance(asset_ids, list):
        asset_ids = []
        assets = []
    else:
        assets = list(DatasetAsset.objects.filter(created_by=request.user, id__in=asset_ids))
    if not assets or len(assets) != len(set(asset_ids)):
        return Response({"code": "invalid_assets", "message": "数据集样本选择不完整"}, status=400)
    if any(asset.annotation_status != DatasetAsset.AnnotationStatus.ANNOTATED for asset in assets):
        return Response({"code": "unannotated_assets", "message": "未标注样本不能加入数据集版本"}, status=409)
    version = DatasetVersion.objects.create(
        name=str(request.data.get("name", "YOLO 数据集")),
        version=str(request.data.get("version", "v1")),
        created_by=request.user,
        class_config=[{"name": value, "display_name": label} for value, label in Annotation.ClassName.choices],
    )
    version.assets.set(assets)
    return Response(_version_payload(version), status=201)


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def freeze_version(request, version_id):
    version = DatasetVersion.objects.select_for_update().filter(id=version_id, created_by=request.user).first()
    if version is None:
        return Response({"code": "dataset_version_not_found", "message": "数据集版本不存在"}, status=404)
    if version.status != DatasetVersion.Status.DRAFT:
        return Response({"code": "dataset_version_immutable", "message": "数据集版本已经冻结，不能重复修改"}, status=409)
    assets = list(version.assets.all())
    if not assets or any(asset.annotation_status != DatasetAsset.AnnotationStatus.ANNOTATED for asset in assets):
        return Response({"code": "unannotated_assets", "message": "数据集版本中的样本必须全部完成标注"}, status=409)
    version.status = DatasetVersion.Status.FROZEN
    version.train_count = round(len(assets) * 0.7)
    version.validation_count = round(len(assets) * 0.2)
    version.test_count = len(assets) - version.train_count - version.validation_count
    version.save(update_fields=("status", "train_count", "validation_count", "test_count"))
    return Response(_version_payload(version))
