import os
import random
import hashlib
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction
from django.utils.timezone import now

from apps.training.services import get_active_model
from apps.uploads.models import MediaAsset, UploadBatch

from .inference import InferenceRequest, InferenceResult
from .models import Detection, RecognitionJob


@dataclass(frozen=True)
class MockDetection:
    sequence: int
    x: float
    y: float
    width: float
    height: float
    label: str
    confidence: float
    reason: str


class MockInferenceAdapter:
    name = "mock"

    def run(self, request: InferenceRequest) -> InferenceResult:
        randomizer = random.Random(f"{request.model_version}:{request.media_id}:{request.input_path.name}")
        results = []
        positions = [(0.06, 0.12), (0.37, 0.1), (0.68, 0.12), (0.08, 0.55), (0.39, 0.52), (0.69, 0.54)]
        for index, (x, y) in enumerate(positions, start=1):
            roll = randomizer.random()
            label = "repair" if roll < 0.16 else "cleaning" if roll < 0.42 else "normal"
            confidence = round(0.64 + randomizer.random() * 0.34, 3)
            reason = ""
            if label == "cleaning":
                reason = "可见表面污染"
            elif label == "repair":
                reason = "检测到可见异常，建议人工复核"
            results.append({
                "sequence": index, "x": x, "y": y, "width": 0.24, "height": 0.31,
                "class": label, "confidence": confidence, "reason": reason,
            })
        return InferenceResult(detections=results, processed_frames=1, total_frames=1)

    def infer(self, checksum):
        """兼容旧的内部调用；新代码统一使用 run(request)。"""
        request = InferenceRequest(
            job_id=0, media_id=0, input_path=Path(checksum), output_dir=Path("."), model_version="mock-v1"
        )
        return [
            MockDetection(
                item["sequence"], item["x"], item["y"], item["width"], item["height"],
                item["class"], item["confidence"], item["reason"],
            )
            for item in self.run(request).detections
        ]


YOLO_CLASS_MAP = {
    "Clean": "normal",
    "Dust": "cleaning",
    "Bird": "repair",
    "Electrical": "repair",
    "Physical": "repair",
    "Snow": "repair",
}


class YoloInferenceAdapter:
    """真实 YOLO 图片推理适配器，供原生 Celery/AI Worker 使用。"""

    name = "yolo"
    _models = {}

    def __init__(self, model_path, expected_sha256=""):
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(f"YOLO 模型不存在: {self.model_path}")
        if expected_sha256:
            digest = hashlib.sha256()
            with self.model_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected_sha256:
                raise ValueError(f"YOLO 模型 SHA-256 校验失败: {self.model_path}")

    @staticmethod
    def _device():
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _model(self):
        key = str(self.model_path.resolve())
        if key not in self._models:
            from ultralytics import YOLO

            self._models[key] = YOLO(key)
        return self._models[key]

    def run(self, request: InferenceRequest) -> InferenceResult:
        if not request.input_path.is_file():
            raise FileNotFoundError(f"输入图片不存在: {request.input_path}")
        request.output_dir.mkdir(parents=True, exist_ok=True)
        model = self._model()
        results = model.predict(
            source=str(request.input_path),
            imgsz=640,
            conf=0.25,
            device=self._device(),
            save=True,
            project=str(request.output_dir),
            name="annotated",
            exist_ok=True,
            verbose=False,
        )
        if not results:
            return InferenceResult(processed_frames=1, total_frames=1)

        result = results[0]
        names = result.names or getattr(model, "names", {})
        detections = []
        boxes = result.boxes
        if boxes is not None:
            xyxyn = boxes.xyxyn.detach().cpu().tolist()
            confidences = boxes.conf.detach().cpu().tolist()
            classes = boxes.cls.detach().cpu().tolist()
            for sequence, (box, confidence, class_id) in enumerate(
                zip(xyxyn, confidences, classes), start=1
            ):
                label = str(names[int(class_id)])
                business_class = YOLO_CLASS_MAP.get(label)
                if business_class is None:
                    continue
                x1, y1, x2, y2 = [max(0.0, min(1.0, float(value))) for value in box]
                detections.append({
                    "sequence": sequence,
                    "model_class": label,
                    "class": business_class,
                    "confidence": round(float(confidence), 4),
                    "x": x1,
                    "y": y1,
                    "width": max(0.0, x2 - x1),
                    "height": max(0.0, y2 - y1),
                    "reason": f"模型识别为 {label}",
                })
        annotated = request.output_dir / "annotated" / request.input_path.name
        return InferenceResult(
            detections=detections,
            processed_frames=1,
            total_frames=1,
            result_file=annotated if annotated.exists() else None,
        )


@transaction.atomic
def execute_job(job_id):
    job = RecognitionJob.objects.select_for_update().select_related("media__batch").get(id=job_id)
    if job.status in {RecognitionJob.Status.RUNNING, RecognitionJob.Status.REVIEW, RecognitionJob.Status.COMPLETED}:
        return job
    job.status = RecognitionJob.Status.RUNNING
    job.progress = 20
    job.started_at = job.started_at or now()
    job.error_message = ""
    job.save(update_fields=("status", "progress", "started_at", "error_message", "updated_at"))
    job.media.status = MediaAsset.Status.PROCESSING
    job.media.save(update_fields=("status",))

    model = job.model_version or get_active_model()
    if job.model_version_id != model.id:
        job.model_version = model
        job.adapter = model.model_type
        job.is_demo_data = model.model_type == "mock"
        job.save(update_fields=("model_version", "adapter", "is_demo_data", "updated_at"))
    input_path = Path(job.media.original_file.path)
    output_dir = Path(job.media.original_file.storage.location) / "results" / str(job.id)
    request = InferenceRequest(
        job_id=job.id,
        media_id=job.media_id,
        input_path=input_path,
        output_dir=output_dir,
        model_version=model.version,
    )
    if model.model_type == model.ModelType.YOLO:
        model_path = Path(model.model_path)
        if not model_path.is_absolute():
            model_path = Path(job.media.original_file.storage.location) / model_path
        result = YoloInferenceAdapter(model_path, model.model_sha256).run(request)
    else:
        result = MockInferenceAdapter().run(request)
    Detection.objects.filter(job=job).delete()
    rows = []
    has_pending = False
    for item in result.detections:
        review_status = Detection.ReviewStatus.PENDING if item["confidence"] < 0.75 else Detection.ReviewStatus.CONFIRMED
        has_pending = has_pending or review_status == Detection.ReviewStatus.PENDING
        rows.append(Detection(
            job=job, sequence=item["sequence"], model_class=item.get("model_class", ""),
            x=item["x"], y=item["y"], width=item["width"], height=item["height"],
            original_class=item["class"], confidence=item["confidence"], reason=item["reason"],
            review_status=review_status, is_demo_data=model.model_type == model.ModelType.MOCK,
        ))
    Detection.objects.bulk_create(rows)

    job.status = RecognitionJob.Status.REVIEW if has_pending else RecognitionJob.Status.COMPLETED
    job.progress = 100
    job.processed_frames = result.processed_frames or job.total_frames
    job.completed_at = None if has_pending else now()
    job.save(update_fields=("status", "progress", "processed_frames", "completed_at", "updated_at"))
    job.media.status = MediaAsset.Status.REVIEW if has_pending else MediaAsset.Status.COMPLETED
    job.media.save(update_fields=("status",))
    _refresh_batch(job.media.batch)
    return job


execute_mock_job = execute_job


def _refresh_batch(batch):
    statuses = set(batch.media_assets.values_list("status", flat=True))
    if statuses and statuses <= {MediaAsset.Status.COMPLETED, MediaAsset.Status.REVIEW}:
        batch.status = UploadBatch.Status.COMPLETED
    elif MediaAsset.Status.FAILED in statuses:
        batch.status = UploadBatch.Status.PARTIAL_FAILED
    else:
        batch.status = UploadBatch.Status.PROCESSING
    batch.save(update_fields=("status", "updated_at"))
