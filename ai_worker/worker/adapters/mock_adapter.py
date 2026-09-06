import random

from .base import InferenceRequest, InferenceResult


class MockInferenceAdapter:
    """原生 Worker 使用的确定性演示适配器，不执行真实模型推理。"""

    def run(self, request: InferenceRequest) -> InferenceResult:
        randomizer = random.Random(f"{request.job_id}:{request.media_id}:{request.input_path.name}")
        labels = ("normal", "cleaning", "repair")
        detections = [
            {
                "sequence": index,
                "class": labels[randomizer.randrange(len(labels))],
                "confidence": round(0.64 + randomizer.random() * 0.34, 3),
                "is_demo_data": True,
            }
            for index in range(1, 7)
        ]
        return InferenceResult(detections=detections, processed_frames=1, total_frames=1)

