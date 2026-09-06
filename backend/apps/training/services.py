import os

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.timezone import now

from apps.accounts.models import AuditLog

from .models import ModelVersion

YOLO_VERSION = "solar-yolo11n-v1"
YOLO_CLASSES = ["normal", "cleaning", "repair"]

def execute_local_training(run):
    """运行可离线演示的轻量训练适配器。

    V1 在没有 MPS/YOLO 训练依赖时仍应能完成任务闭环；这里生成可审计的
    演示模型记录，并明确标记为 mock，不把演示指标冒充真实模型评估结果。
    """
    from .models import ModelVersion, TrainingRun

    run.status = TrainingRun.Status.RUNNING
    run.progress = 20
    run.started_at = now()
    run.save(update_fields=("status", "progress", "started_at"))
    sample_count = run.dataset_version.assets.count()
    run.metrics = {
        "mode": "offline_demo",
        "sample_count": sample_count,
        "precision": 0.0,
        "recall": 0.0,
        "map50": 0.0,
        "note": "演示训练适配器未执行真实模型训练，需使用 YOLO Worker 生成正式指标",
    }
    model = ModelVersion.objects.create(
        name=f"离线训练演示模型 · {run.dataset_version.version}",
        version=f"offline-{run.id}", model_type=ModelVersion.ModelType.MOCK,
        status=ModelVersion.Status.CANDIDATE, model_path="",
        dataset_version=run.dataset_version, metrics=run.metrics,
        class_config=YOLO_CLASSES, created_by=run.created_by,
    )
    run.output_model_version = model
    run.status = TrainingRun.Status.COMPLETED
    run.progress = 100
    run.completed_at = now()
    run.save(update_fields=("output_model_version", "metrics", "status", "progress", "completed_at"))
    return run


def get_or_create_mock_model():
    user_model = get_user_model()
    owner = user_model.objects.filter(is_superuser=True).first() or user_model.objects.order_by("id").first()
    if owner is None:
        raise RuntimeError("创建识别作业前必须先创建用户")
    model, _ = ModelVersion.objects.get_or_create(
        version="mock-v1",
        defaults={
            "name": "离线演示模型", "model_type": ModelVersion.ModelType.MOCK,
            "status": ModelVersion.Status.ACTIVE, "is_active": True,
            "class_config": ["normal", "cleaning", "repair"], "created_by": owner,
            "activated_by": owner, "activated_at": now(),
        },
    )
    return model


def get_active_model():
    return ModelVersion.objects.filter(is_active=True, status=ModelVersion.Status.ACTIVE).order_by("-activated_at").first() or get_or_create_mock_model()


def get_or_create_yolo_model(owner, activate=False):
    model_path = os.getenv("YOLO_MODEL_PATH", "models/solar-yolo11n-v1.pt")
    model, created = ModelVersion.objects.get_or_create(
        version=YOLO_VERSION,
        defaults={
            "name": "Solar YOLO11-nano 三类巡检模型",
            "model_type": ModelVersion.ModelType.YOLO,
            "model_path": model_path,
            "status": ModelVersion.Status.CANDIDATE,
            "class_config": YOLO_CLASSES,
            "created_by": owner,
        },
    )
    if not created and model.model_path != model_path:
        model.model_path = model_path
        model.save(update_fields=("model_path",))
    if activate and not model.is_active:
        activate_model(model, owner)
    return model


@transaction.atomic
def activate_model(model, operator):
    if model.status not in {ModelVersion.Status.CANDIDATE, ModelVersion.Status.RETIRED}:
        raise ValueError("只有候选或已退役模型可以启用")
    ModelVersion.objects.filter(is_active=True).update(is_active=False, status=ModelVersion.Status.RETIRED)
    model.status = ModelVersion.Status.ACTIVE
    model.is_active = True
    model.activated_by = operator
    model.activated_at = now()
    model.save(update_fields=("status", "is_active", "activated_by", "activated_at"))
    AuditLog.objects.create(
        operator=operator,
        action_type=AuditLog.ActionType.MODEL_SWITCH,
        reason=f"切换当前模型为 {model.version}",
    )
    return model
