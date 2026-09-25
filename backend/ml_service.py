"""
Plant disease classification service (Phase 1 + Phase 3 hardening).

Preserved from Version 1
    * MobileNetV2 fine-tuned image classifier (38 classes) loaded from
      ``backend/models/plant_disease_model``
    * top-k probability list (default 5) returned to the UI
    * base64 image preview returned to the UI

Fixed / improved (PROJECT_AUDIT.md §6)
    * inference device is resolved from config (GPU is used when available)
    * ``is_healthy`` is derived from the predicted label, not hardcoded False
    * ``severity`` comes from a documented keyword mapping instead of confidence
    * a confidence floor flags low-confidence / out-of-distribution images as
      "uncertain" instead of returning a confident disease name
    * the returned image is genuinely annotated (top-1 label + confidence drawn
      onto the image); the field is no longer misleading
    * inference time is measured and returned for the performance section

Honest limitations (documented for the paper)
    * the annotation is a caption, not a bounding box or a Grad-CAM heatmap; the
      model performs image classification, not object localisation
    * the severity mapping is a heuristic over class-name keywords and is NOT
      clinically or agronomically validated
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

# Windows raised OSError: [Errno 22] from tqdm in Version 1; disabling the HF
# progress bars is the real fix (the stderr guard stays as a safety net).
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
if hasattr(sys.stderr, "flush"):
    _original_flush = sys.stderr.flush

    def _safe_flush():
        try:
            _original_flush()
        except OSError:
            pass

    sys.stderr.flush = _safe_flush  # type: ignore[assignment]

from PIL import Image, ImageDraw  # noqa: E402
from transformers import pipeline  # noqa: E402
from transformers.utils import logging as hf_logging  # noqa: E402

from app.config import settings  # noqa: E402
from app.logging_config import get_logger  # noqa: E402

hf_logging.disable_progress_bar()

logger = get_logger("ml_service")

detector = None
_model_device: str = "not-loaded"

HEALTHY_KEYWORDS = ("healthy",)
# Documented heuristic mapping (class-name keyword -> severity band).
SEVERITY_RULES: List[tuple[tuple[str, ...], str]] = [
    (
        (
            "late blight",
            "black rot",
            "esca",
            "greening",
            "scorch",
            "northern leaf blight",
            "bacterial spot",
            "cercospora",
        ),
        "High",
    ),
    (
        ("early blight", "leaf spot", "powdery mildew", "scab", "rust", "mildew", "measles"),
        "Moderate",
    ),
]


def resolve_device() -> int:
    """Return the transformers device index: 0 for CUDA, -1 for CPU."""
    wanted = (settings.ml_device or "auto").lower()
    if wanted == "cpu":
        return -1
    if wanted in {"cuda", "gpu"}:
        return 0
    try:  # auto - torch imported lazily so the API still boots without it
        import torch

        return 0 if torch.cuda.is_available() else -1
    except Exception:  # pragma: no cover
        return -1


def load_or_download_model():
    """Load the classifier once per process (idempotent)."""
    global detector, _model_device
    if detector is not None:
        return detector

    model_path = str(settings.model_dir)
    if not os.path.isdir(model_path):
        raise FileNotFoundError(
            f"Plant disease model not found at '{model_path}'. "
            "Place the fine-tuned model there or set MODEL_DIR in the environment."
        )

    device = resolve_device()
    _model_device = "cuda" if device == 0 else "cpu"
    started = time.perf_counter()
    logger.info("Loading plant disease model from %s (device=%s)", model_path, _model_device)
    detector = pipeline("image-classification", model=model_path, device=device)
    logger.info(
        "Model loaded in %.2fs (device=%s, top_k=%s)",
        time.perf_counter() - started,
        _model_device,
        settings.ml_top_k,
    )
    return detector


def model_info() -> Dict[str, Any]:
    """
    Model metadata for logging and the system endpoint.

    Only the leaf folder name is exposed: the absolute path describes the host
    filesystem layout and has no business being readable over HTTP.
    """
    return {
        "model_name": settings.model_dir.name,
        "device": _model_device,
        "top_k": settings.ml_top_k,
        "confidence_floor": settings.ml_confidence_floor,
        "num_labels": _num_labels(),
        "loaded": detector is not None,
    }


def _num_labels() -> Optional[int]:
    """Number of output classes, read from the model config when available."""
    config_file = settings.model_dir / "config.json"
    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            config = json.load(handle)
        id2label = config.get("id2label") or {}
        return len(id2label) or None
    except (OSError, ValueError, TypeError):
        return None


def severity_from_label(label: str) -> str:
    """Heuristic severity band from the predicted class name (see module docstring)."""
    lowered = (label or "").lower()
    if any(key in lowered for key in HEALTHY_KEYWORDS):
        return "None"
    for keywords, band in SEVERITY_RULES:
        if any(key in lowered for key in keywords):
            return band
    return "Moderate"


def is_healthy_label(label: str) -> bool:
    return any(key in (label or "").lower() for key in HEALTHY_KEYWORDS)


def _annotate(image: Image.Image, caption: str) -> str:
    """Draw the top prediction onto the image and return base64 JPEG."""
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    text = caption[:70]
    padding = 6
    try:
        bbox = draw.textbbox((0, 0), text)
        text_height = bbox[3] - bbox[1]
    except Exception:  # pragma: no cover - very old Pillow
        text_height = 12
    bar_height = text_height + 2 * padding
    draw.rectangle([0, 0, annotated.width, bar_height], fill=(0, 0, 0))
    draw.text((padding, padding), text, fill=(255, 255, 255))

    buffer = io.BytesIO()
    annotated.save(buffer, format="JPEG", quality=88)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def predict_image(image_bytes: bytes, top_k: Optional[int] = None) -> Dict[str, Any]:
    """
    Classify a leaf image.

    Raises ``ValueError`` when the payload is not a readable/usable image so the
    API can return a clean 400 instead of a 500.
    """
    model = load_or_download_model()

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        image = image.convert("RGB")
    except Exception as exc:  # noqa: BLE001 - convert to a validation error
        raise ValueError(f"Unreadable image file: {exc}") from exc

    if image.width < settings.min_image_dimension or image.height < settings.min_image_dimension:
        raise ValueError(
            f"Image is too small ({image.width}x{image.height}px). "
            f"Minimum dimension is {settings.min_image_dimension}px."
        )

    if image.width * image.height > settings.max_image_pixels:
        raise ValueError("Image resolution is too large to process safely.")

    started = time.perf_counter()
    raw_results = model(image, top_k=top_k or settings.ml_top_k)
    inference_ms = round((time.perf_counter() - started) * 1000, 1)

    detections = sorted(
        (
            {
                "label": str(result.get("label", "Unknown")),
                "score": round(float(result.get("score", 0.0)) * 100, 2),
                "box": None,  # classification model: no localisation available
            }
            for result in raw_results
        ),
        key=lambda item: item["score"],
        reverse=True,
    )

    top = detections[0] if detections else {"label": "Unknown", "score": 0.0}
    confident = bool(detections) and top["score"] >= settings.ml_confidence_floor
    healthy = is_healthy_label(top["label"])

    if not detections:
        status = "unknown"
    elif not confident:
        status = "uncertain"
    elif healthy:
        status = "healthy"
    else:
        status = "diseased"

    caption = f"{top['label']} - {top['score']}%" if detections else "No prediction available"

    return {
        "detections": detections,
        "status": status,
        "top_label": top["label"],
        "top_score": top["score"],
        "is_healthy": healthy,
        "severity": "None" if healthy else severity_from_label(top["label"]),
        "confident": confident,
        "confidence_floor": settings.ml_confidence_floor,
        "requires_expert_review": not confident,
        "inference_ms": inference_ms,
        "device": _model_device,
        "annotation_type": "prediction_caption",
        "annotated_image_base64": _annotate(image, caption),
    }

