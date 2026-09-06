from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class InferenceRequest:
    job_id: int
    media_id: int
    input_path: Path
    output_dir: Path
    model_version: str
    threshold: float = 0.75
    sample_fps: int = 3


@dataclass
class InferenceResult:
    detections: list[dict] = field(default_factory=list)
    processed_frames: int = 0
    total_frames: int = 0
    result_file: Path | None = None
    keyframes: list[Path] = field(default_factory=list)
    error: str = ""


class InferenceAdapter(Protocol):
    name: str

    def run(self, request: InferenceRequest) -> InferenceResult: ...
