from pathlib import Path

from .base import InferenceRequest, InferenceResult

YOLO_CLASS_MAP = {
    "Clean": "normal",
    "Dust": "cleaning",
    "Bird": "repair",
    "Electrical": "repair",
    "Physical": "repair",
    "Snow": "repair",
}


class YoloInferenceAdapter:
    """原生 AI Worker 使用的 YOLOv11 图片适配器。"""

    name = "yolo"
    _models = {}

    def __init__(self, model_path):
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(f"YOLO 模型不存在: {self.model_path}")

    def _device(self):
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
        result = model.predict(
            source=str(request.input_path), imgsz=640, conf=0.25,
            device=self._device(), save=True, project=str(request.output_dir),
            name="annotated", exist_ok=True, verbose=False,
        )[0]
        detections = []
        names = result.names or getattr(model, "names", {})
        if result.boxes is not None:
            for sequence, (box, confidence, class_id) in enumerate(zip(
                result.boxes.xyxyn.detach().cpu().tolist(),
                result.boxes.conf.detach().cpu().tolist(),
                result.boxes.cls.detach().cpu().tolist(),
            ), start=1):
                label = str(names[int(class_id)])
                if label not in YOLO_CLASS_MAP:
                    continue
                x1, y1, x2, y2 = box
                detections.append({
                    "sequence": sequence, "model_class": label,
                    "class": YOLO_CLASS_MAP[label], "confidence": round(float(confidence), 4),
                    "x": max(0.0, min(1.0, x1)), "y": max(0.0, min(1.0, y1)),
                    "width": max(0.0, min(1.0, x2 - x1)),
                    "height": max(0.0, min(1.0, y2 - y1)),
                    "reason": f"模型识别为 {label}",
                })
        annotated = request.output_dir / "annotated" / request.input_path.name
        return InferenceResult(
            detections=detections, processed_frames=1, total_frames=1,
            result_file=annotated if annotated.exists() else None,
        )
