from django.db import transaction
from django.utils.timezone import now
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator
from apps.datasets.models import DatasetVersion

from .models import ModelVersion, TrainingRun
from .serializers import model_payload, run_payload
from .services import activate_model, execute_local_training, get_or_create_mock_model


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def model_collection(request):
    get_or_create_mock_model()
    return Response({"results": [model_payload(item) for item in ModelVersion.objects.all()]})


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def model_detail(request, model_id):
    model = ModelVersion.objects.filter(id=model_id).first()
    if model is None:
        return Response({"code": "model_not_found", "message": "模型版本不存在"}, status=404)
    return Response(model_payload(model))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def activate(request, model_id):
    model = ModelVersion.objects.filter(id=model_id).first()
    if model is None:
        return Response({"code": "model_not_found", "message": "模型版本不存在"}, status=404)
    try:
        model = activate_model(model, request.user)
    except ValueError as exc:
        return Response({"code": "model_not_activatable", "message": str(exc)}, status=409)
    return Response(model_payload(model))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def rollback(request, model_id):
    model = ModelVersion.objects.filter(id=model_id).first()
    if model is None:
        return Response({"code": "model_not_found", "message": "模型版本不存在"}, status=404)
    if model.status != ModelVersion.Status.RETIRED:
        return Response({"code": "model_not_rollbackable", "message": "只有已退役模型可以回滚"}, status=409)
    return Response(model_payload(activate_model(model, request.user)))


@api_view(["GET", "POST"])
@permission_classes([IsApprovedOperator])
def run_collection(request):
    if request.method == "GET":
        runs = TrainingRun.objects.filter(created_by=request.user).select_related("dataset_version")
        return Response({"results": [run_payload(item) for item in runs]})
    dataset = DatasetVersion.objects.filter(id=request.data.get("dataset_version_id"), created_by=request.user).first()
    if dataset is None:
        return Response({"code": "dataset_version_not_found", "message": "数据集版本不存在"}, status=404)
    if dataset.status != DatasetVersion.Status.FROZEN:
        return Response({"code": "dataset_not_frozen", "message": "只有冻结后的数据集版本可以训练"}, status=409)
    base_model = ModelVersion.objects.filter(is_active=True).first() or get_or_create_mock_model()
    try:
        epochs = int(request.data.get("epochs", 50))
        image_size = int(request.data.get("image_size", 1024))
        batch_size = int(request.data.get("batch_size", 16))
    except (TypeError, ValueError):
        return Response({"code": "invalid_training_config", "message": "训练参数必须是数字"}, status=400)
    if not 20 <= epochs <= 100 or image_size not in {640, 768, 1024, 1280} or not 1 <= batch_size <= 64:
        return Response({"code": "invalid_training_config", "message": "训练参数超出允许范围"}, status=400)
    run = TrainingRun.objects.create(
        dataset_version=dataset, base_model_version=base_model,
        epochs=epochs, image_size=image_size, batch_size=batch_size,
        device=str(request.data.get("device", "cuda")),
        status=TrainingRun.Status.CREATED, created_by=request.user,
    )
    run = execute_local_training(run)
    return Response({**run_payload(run), "message": "离线演示训练已完成；正式模型请在 YOLO Worker 中训练"}, status=201)


def _owned_run(user, run_id):
    query = TrainingRun.objects.filter(id=run_id)
    return query.first() if user.is_superuser else query.filter(created_by=user).first()


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def run_detail(request, run_id):
    run = _owned_run(request.user, run_id)
    if run is None:
        return Response({"code": "training_run_not_found", "message": "训练任务不存在"}, status=404)
    return Response(run_payload(run))


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
@transaction.atomic
def cancel_run(request, run_id):
    run = _owned_run(request.user, run_id)
    if run is None:
        return Response({"code": "training_run_not_found", "message": "训练任务不存在"}, status=404)
    if run.status not in {TrainingRun.Status.CREATED, TrainingRun.Status.QUEUED, TrainingRun.Status.RUNNING}:
        return Response({"code": "training_run_not_cancellable", "message": "当前训练状态不能取消"}, status=409)
    run.status = TrainingRun.Status.CANCELLED
    run.completed_at = now()
    run.save(update_fields=("status", "completed_at"))
    return Response(run_payload(run))


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def run_logs(request, run_id):
    run = _owned_run(request.user, run_id)
    if run is None:
        return Response({"code": "training_run_not_found", "message": "训练任务不存在"}, status=404)
    return Response({"training_run_id": run.id, "status": run.status, "log_file": run.log_file, "logs": []})


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def run_metrics(request, run_id):
    run = _owned_run(request.user, run_id)
    if run is None:
        return Response({"code": "training_run_not_found", "message": "训练任务不存在"}, status=404)
    return Response({"training_run_id": run.id, "metrics": run.metrics})
