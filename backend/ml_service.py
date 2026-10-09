"""
Plant disease classification service (Phase 1 + Phase 3 hardening + ensemble).

Model layer
    A registry of three diverse classifiers that share the same 38-class
    PlantVillage label space:
        * ``mobilenetv2`` - local fine-tuned weights (backend/models/plant_disease_model)
        * ``resnet50``    - HuggingFace ``SanketJadhav/PlantDiseaseClassifier-Resnet50``
        * ``swin``        - HuggingFace ``surgeonwz/plant-village``
    Models load lazily (only when first requested) and are cached per process.
    Hub labels use the raw PlantVillage naming convention, so every label is
    canonicalised to the local model's wording before voting.

Ensemble
    The caller selects any subset of the registry (``models`` form field):
        * one model  -> single-model result, same shape as before
        * 2+ models  -> hard voting: every model casts one top-1 vote for a
          canonical class; the class with the most votes wins, ties broken by
          the summed confidence of its voters. ``agreement`` reports the vote
          share of the winner and ``votes`` lists every model's ballot.

Optimisations
    * the upload is decoded and validated once, then shared by all models
    * models are pre-loaded sequentially (no concurrent first-load races),
      inference runs in a thread pool on CPU; CUDA runs sequentially because
      one GPU already saturates the device (ML_PARALLEL=false disables it)
    * a failing model abstains instead of failing the whole request

Preserved from Version 1 / Phase 3
    * top-k list, confidence floor -> "uncertain", severity keyword mapping,
      genuine caption annotation, inference timing, device reporting
    * honest limitations: the annotation is a caption (not a box or Grad-CAM)
      and the severity mapping is a heuristic, not agronomically validated
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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

# --------------------------------------------------------------------------
# Model registry
# --------------------------------------------------------------------------
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "resnet50_finetuned": {
        "label": "ResNet-50 (Fine-Tuned 281-Class, Val Acc 88.97%)",
        "source": "checkpoints/best_resnet50_plant_disease.pth",
        "source_type": "local_pth",
        "arch": "resnet50",
    },
    "convnext_finetuned": {
        "label": "ConvNeXt-Tiny (Fine-Tuned 281-Class, Val Acc 89.42%, Test Acc 89.54%)",
        "source": "checkpoints/best_convnext_plant_disease.pth",
        "source_type": "local_pth",
        "arch": "convnext",
    },
    "mobilenetv2_finetuned": {
        "label": "MobileNetV2 (Fine-Tuned 332-Class)",
        "source": None,  # local weights: settings.finetuned_model_path
        "source_type": "local_pth",
        "arch": "mobilenetv2",
    },
    "mobilenetv2": {
        "label": "MobileNetV2 (38-Class Base)",
        "source": None,  # local folder: settings.model_dir
        "source_type": "local",
    },
    "resnet50": {
        "label": "ResNet-50",
        "source": "SanketJadhav/PlantDiseaseClassifier-Resnet50",
        "source_type": "hub",
    },
    "swin": {
        "label": "Swin-Tiny",
        "source": "surgeonwz/plant-village",
        "source_type": "hub",
    },
}

# Raw PlantVillage label -> the local model's label (same 38 classes, other
# naming). Unknown labels pass through untouched and simply abstain in a vote.
_PLANTVILLAGE_TO_CANONICAL: Dict[str, str] = {
    "Apple___Apple_scab": "Apple Scab",
    "Apple___Black_rot": "Apple with Black Rot",
    "Apple___Cedar_apple_rust": "Cedar Apple Rust",
    "Apple___healthy": "Healthy Apple",
    "Blueberry___healthy": "Healthy Blueberry Plant",
    "Cherry_(including_sour)___Powdery_mildew": "Cherry with Powdery Mildew",
    "Cherry_(including_sour)___healthy": "Healthy Cherry Plant",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "Corn (Maize) with Cercospora and Gray Leaf Spot",
    "Corn_(maize)___Common_rust_": "Corn (Maize) with Common Rust",
    "Corn_(maize)___Northern_Leaf_Blight": "Corn (Maize) with Northern Leaf Blight",
    "Corn_(maize)___healthy": "Healthy Corn (Maize) Plant",
    "Grape___Black_rot": "Grape with Black Rot",
    "Grape___Esca_(Black_Measles)": "Grape with Esca (Black Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": "Grape with Isariopsis Leaf Spot",
    "Grape___healthy": "Healthy Grape Plant",
    "Orange___Haunglongbing_(Citrus_greening)": "Orange with Citrus Greening",
    "Peach___Bacterial_spot": "Peach with Bacterial Spot",
    "Peach___healthy": "Healthy Peach Plant",
    "Pepper,_bell___Bacterial_spot": "Bell Pepper with Bacterial Spot",
    "Pepper,_bell___healthy": "Healthy Bell Pepper Plant",
    "Potato___Early_blight": "Potato with Early Blight",
    "Potato___Late_blight": "Potato with Late Blight",
    "Potato___healthy": "Healthy Potato Plant",
    "Raspberry___healthy": "Healthy Raspberry Plant",
    "Soybean___healthy": "Healthy Soybean Plant",
    "Squash___Powdery_mildew": "Squash with Powdery Mildew",
    "Strawberry___Leaf_scorch": "Strawberry with Leaf Scorch",
    "Strawberry___healthy": "Healthy Strawberry Plant",
    "Tomato___Bacterial_spot": "Tomato with Bacterial Spot",
    "Tomato___Early_blight": "Tomato with Early Blight",
    "Tomato___Late_blight": "Tomato with Late Blight",
    "Tomato___Leaf_Mold": "Tomato with Leaf Mold",
    "Tomato___Septoria_leaf_spot": "Tomato with Septoria Leaf Spot",
    "Tomato___Spider_mites Two-spotted_spider_mite": "Tomato with Spider Mites or Two-spotted Spider Mite",
    "Tomato___Target_Spot": "Tomato with Target Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": "Tomato Yellow Leaf Curl Virus",
    "Tomato___Tomato_mosaic_virus": "Tomato Mosaic Virus",
    "Tomato___healthy": "Healthy Tomato Plant",
}

_pipelines: Dict[str, Any] = {}
_load_lock = threading.Lock()
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


def parse_model_selection(models: Optional[str]) -> List[str]:
    """
    Turn the request's ``models`` field into an ordered registry id list.

    Empty input falls back to ``ML_DEFAULT_MODELS``; unknown ids and an empty
    selection raise ``ValueError`` (the endpoint maps it to HTTP 400).
    """
    raw = (models or "").strip()
    if not raw:
        raw = settings.ml_default_models
    ordered: List[str] = []
    for token in raw.split(","):
        model_id = token.strip().lower()
        if model_id and model_id not in ordered:
            ordered.append(model_id)
    if not ordered:
        raise ValueError("Select at least one model.")
    unknown = [m for m in ordered if m not in MODEL_REGISTRY]
    if unknown:
        raise ValueError(
            f"Unknown model(s): {', '.join(unknown)}. "
            f"Available: {', '.join(MODEL_REGISTRY)}."
        )
    return ordered


class PyTorchLocalPipeline:
    """Callable pipeline interface matching transformers pipeline('image-classification') for custom PyTorch weights."""

    def __init__(self, model_path: str, id2label_path: str, device: str = "cpu", arch: str = "mobilenetv2") -> None:
        import torch
        import torchvision.models as tv_models
        import torchvision.transforms as tv_transforms

        self.device = torch.device(device)
        self.transform = tv_transforms.Compose([
            tv_transforms.Resize((224, 224)),
            tv_transforms.ToTensor(),
            tv_transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        with open(id2label_path, "r", encoding="utf-8") as f:
            raw_map = json.load(f)
            self.id2label = {int(k): str(v) for k, v in raw_map.items()}

        num_classes = len(self.id2label)
        if arch.lower() == "resnet50":
            net = tv_models.resnet50(weights=None)
            net.fc = torch.nn.Sequential(
                torch.nn.Dropout(p=0.4),
                torch.nn.Linear(net.fc.in_features, num_classes)
            )
        elif arch.lower() in {"convnext", "convnext_tiny"}:
            net = tv_models.convnext_tiny(weights=None)
            net.classifier[2] = torch.nn.Sequential(
                torch.nn.Dropout(p=0.3),
                torch.nn.Linear(net.classifier[2].in_features, num_classes)
            )
        else:
            net = tv_models.mobilenet_v2()
            net.classifier[1] = torch.nn.Linear(net.classifier[1].in_features, num_classes)

        state_dict = torch.load(model_path, map_location=self.device)
        if "model_state_dict" in state_dict:
            state_dict = state_dict["model_state_dict"]
        net.load_state_dict(state_dict)
        net.to(self.device)
        net.eval()
        self.net = net
        self.torch = torch

    def __call__(self, image: Image.Image, top_k: int = 5) -> List[Dict[str, Any]]:
        img_rgb = image.convert("RGB")
        tensor = self.transform(img_rgb).unsqueeze(0).to(self.device)
        with self.torch.no_grad():
            outputs = self.net(tensor)
            probs = self.torch.softmax(outputs, dim=1).squeeze(0)
            k = min(top_k, len(probs))
            top_probs, top_indices = self.torch.topk(probs, k=k)

        results = []
        for score, idx in zip(top_probs.tolist(), top_indices.tolist()):
            label_name = self.id2label.get(idx, f"Class_{idx}")
            results.append({"label": label_name, "score": float(score)})
        return results


def load_model(model_id: str) -> Any:
    """Load one registry pipeline once per process (thread-safe, idempotent)."""
    global _model_device
    cached = _pipelines.get(model_id)
    if cached is not None:
        return cached
    with _load_lock:
        cached = _pipelines.get(model_id)
        if cached is not None:
            return cached

        spec = MODEL_REGISTRY[model_id]
        device = resolve_device()
        device_str = "cuda" if device == 0 else "cpu"
        _model_device = device_str

        if spec["source_type"] == "local_pth":
            arch = spec.get("arch", "mobilenetv2")
            if arch.lower() == "resnet50":
                pth_candidates = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "best_resnet50_plant_disease.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", "best_resnet50_plant_disease.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "best_resnet50_plant_disease.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "latest_checkpoint.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", "latest_checkpoint.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dhanu", "checkpoints", "best_resnet50_plant_disease.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dhanu", "checkpoints", "latest_checkpoint.pth")),
                ]
                pth_path = next((c for c in pth_candidates if os.path.isfile(c)), None)
                if not pth_path:
                    raise FileNotFoundError("Fine-tuned ResNet-50 checkpoint not found in checkpoints/.")

                id2label_candidates = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "id2label_resnet50.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", "id2label_resnet50.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "id2label_resnet50.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dhanu", "checkpoints", "id2label_resnet50.json")),
                ]
                id2label_path = next((c for c in id2label_candidates if os.path.isfile(c)), None)
                if not id2label_path:
                    raise FileNotFoundError("ResNet-50 281-class mapping (id2label_resnet50.json) not found in checkpoints/.")
            elif arch.lower() in {"convnext", "convnext_tiny"}:
                pth_candidates = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "best_convnext_plant_disease.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", "best_convnext_plant_disease.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "best_convnext_plant_disease.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "latest_convnext_checkpoint.pth")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", "latest_convnext_checkpoint.pth")),
                ]
                pth_path = next((c for c in pth_candidates if os.path.isfile(c)), None)
                if not pth_path:
                    raise FileNotFoundError("Fine-tuned ConvNeXt checkpoint not found in checkpoints/.")

                id2label_candidates = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "id2label_convnext.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", "id2label_convnext.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "id2label_resnet50.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", "id2label_resnet50.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "id2label_resnet50.json")),
                ]
                id2label_path = next((c for c in id2label_candidates if os.path.isfile(c)), None)
                if not id2label_path:
                    raise FileNotFoundError("ConvNeXt label mapping not found in checkpoints/.")
            else:
                pth_path = str(settings.finetuned_model_path)
                id2label_path = str(settings.id2label_path)
                if not os.path.isfile(pth_path):
                    candidates = [
                        os.path.join(str(settings.model_dir), "best_plant_model.pth"),
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "best_mobilenetv2_plant_disease.pth")),
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "best_plant_model.pth")),
                    ]
                    for cand in candidates:
                        if os.path.isfile(cand):
                            pth_path = os.path.abspath(cand)
                            break
                    else:
                        raise FileNotFoundError(
                            f"Fine-tuned plant disease model not found at '{pth_path}'."
                        )
                if not os.path.isfile(id2label_path):
                    alt_candidates = [
                        os.path.join(os.path.dirname(pth_path), "id2label.json"),
                        os.path.join(str(settings.model_dir), "id2label.json"),
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "id2label.json")),
                    ]
                    for cand in alt_candidates:
                        if os.path.isfile(cand):
                            id2label_path = os.path.abspath(cand)
                            break
                    else:
                        raise FileNotFoundError(
                            f"Label mapping file not found at '{id2label_path}'."
                        )

            started = time.perf_counter()
            logger.info("Loading fine-tuned PyTorch model from %s (device=%s, arch=%s)", pth_path, _model_device, arch)
            try:
                pipe = PyTorchLocalPipeline(pth_path, id2label_path, device=device_str, arch=arch)
                _pipelines[model_id] = pipe
                logger.info("Model '%s' loaded in %.2fs", model_id, time.perf_counter() - started)
                return pipe
            except ImportError as err:
                logger.warning("torchvision not installed (%s). Falling back to base MobileNetV2 model.", err)
                if "mobilenetv2" in MODEL_REGISTRY:
                    fallback_pipe = load_model("mobilenetv2")
                    _pipelines[model_id] = fallback_pipe
                    return fallback_pipe
                raise

        source = str(settings.model_dir) if spec["source_type"] == "local" else spec["source"]
        if spec["source_type"] == "local" and not os.path.isdir(source):
            if os.path.isfile(source) and (source.endswith(".pth") or source.endswith(".pt")):
                id2label_path = str(settings.id2label_path)
                pipe = PyTorchLocalPipeline(source, id2label_path, device=device_str)
                _pipelines[model_id] = pipe
                return pipe
            raise FileNotFoundError(
                f"Plant disease model not found at '{source}'. "
                "Place the fine-tuned model there or set MODEL_DIR in the environment."
            )

        started = time.perf_counter()
        logger.info("Loading model '%s' from %s (device=%s)", model_id, source, _model_device)
        pipe = pipeline("image-classification", model=source, device=device)
        _pipelines[model_id] = pipe
        logger.info("Model '%s' loaded in %.2fs", model_id, time.perf_counter() - started)
        return pipe


def load_or_download_model() -> Any:
    """Warm the default model selection (kept for the startup hook)."""
    model_ids = parse_model_selection(None)
    first = None
    for model_id in model_ids:
        loaded = load_model(model_id)
        if first is None:
            first = loaded
    return first


def available_models() -> List[Dict[str, Any]]:
    """Registry entries plus their current load state (for the UI/API info)."""
    return [
        {
            "id": model_id,
            "label": spec["label"],
            "source_type": spec["source_type"],
            "loaded": model_id in _pipelines,
        }
        for model_id, spec in MODEL_REGISTRY.items()
    ]


def model_info() -> Dict[str, Any]:
    """
    Model metadata for logging and the system endpoint.

    Only the local folder name is exposed: the absolute path describes the host
    filesystem layout and has no business being readable over HTTP.
    """
    return {
        "model_name": settings.model_dir.name,
        "registry": available_models(),
        "default_models": parse_model_selection(None),
        "device": _model_device,
        "top_k": settings.ml_top_k,
        "confidence_floor": settings.ml_confidence_floor,
        "num_labels": _num_labels(),
        "loaded": bool(_pipelines),
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


def canonical_label(raw_label: str) -> str:
    """Map a model's own label onto the shared 38-class wording."""
    text = str(raw_label or "").strip()
    return _PLANTVILLAGE_TO_CANONICAL.get(text, text)


def _annotate(image: Image.Image, caption: str) -> str:
    """Draw the winning prediction onto the image and return base64 JPEG."""
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


def _predict_one(model_id: str, image: Image.Image, top_k: int) -> Dict[str, Any]:
    """Run one model and normalise its output (a failure becomes an abstention)."""
    started = time.perf_counter()
    try:
        pipe = load_model(model_id)
        raw_results = pipe(image, top_k=top_k)
    except Exception as exc:  # noqa: BLE001 - one bad model must not kill the vote
        logger.error("Model '%s' failed, abstaining from the vote: %s", model_id, exc)
        err_msg = str(exc).strip().split("\n")[0]
        if "image processor" in err_msg.lower() or "preprocessor" in err_msg.lower():
            err_msg = "Hub model preprocessor incompatible"
        elif "connection" in err_msg.lower() or "timeout" in err_msg.lower():
            err_msg = "Hub download connection timeout"
        elif len(err_msg) > 60:
            err_msg = err_msg[:57] + "..."
        return {
            "id": model_id,
            "label": MODEL_REGISTRY[model_id]["label"],
            "ok": False,
            "error": err_msg,
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "detections": [],
            "top_label": None,
            "top_score": 0.0,
        }

    detections = sorted(
        (
            {
                "label": canonical_label(result.get("label", "Unknown")),
                "raw_label": str(result.get("label", "Unknown")),
                "score": round(float(result.get("score", 0.0)) * 100, 2),
                "box": None,  # classification model: no localisation available
            }
            for result in raw_results
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    top = detections[0] if detections else {"label": "Unknown", "score": 0.0}
    return {
        "id": model_id,
        "label": MODEL_REGISTRY[model_id]["label"],
        "ok": True,
        "error": None,
        "ms": round((time.perf_counter() - started) * 1000, 1),
        "detections": detections,
        "top_label": top["label"],
        "top_score": top["score"],
    }


def _hard_vote(outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Majority vote over the models' top-1 labels; ties go to higher summed confidence."""
    tally: Dict[str, Dict[str, Any]] = {}
    for outcome in outcomes:
        entry = tally.setdefault(outcome["top_label"], {"label": outcome["top_label"], "votes": 0, "score_sum": 0.0})
        entry["votes"] += 1
        entry["score_sum"] += outcome["top_score"]
    winner = max(tally.values(), key=lambda e: (e["votes"], e["score_sum"]))
    total_votes = max(1, sum(e["votes"] for e in tally.values()))
    return {
        "label": winner["label"],
        "votes": winner["votes"],
        "score": round(winner["score_sum"] / winner["votes"], 2),
        "agreement": round(100.0 * winner["votes"] / total_votes, 1),
    }


def _merge_detections(outcomes: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """Rank the union of every model's top-k by (votes, mean confidence)."""
    merged: Dict[str, Dict[str, Any]] = {}
    for outcome in outcomes:
        for det in outcome["detections"]:
            entry = merged.setdefault(
                det["label"],
                {"label": det["label"], "score_sum": 0.0, "n": 0, "votes": 0},
            )
            entry["score_sum"] += det["score"]
            entry["n"] += 1
        winner_slot = merged.get(outcome["top_label"])
        if winner_slot is not None:
            winner_slot["votes"] += 1
    ranked = sorted(
        merged.values(),
        key=lambda e: (e["votes"], e["score_sum"] / max(1, e["n"])),
        reverse=True,
    )
    return [
        {
            "label": entry["label"],
            "score": round(entry["score_sum"] / max(1, entry["n"]), 2),
            "votes": entry["votes"],
            "box": None,
        }
        for entry in ranked[:top_k]
    ]


def predict_image(
    image_bytes: bytes,
    top_k: Optional[int] = None,
    model_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Classify a leaf image with the selected model subset.

    Raises ``ValueError`` when the payload is not a readable/usable image or the
    model selection is invalid so the API can return a clean 400 instead of a 500.
    """
    selected = parse_model_selection(None if model_ids is None else ",".join(model_ids))

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

    k = top_k or settings.ml_top_k
    started = time.perf_counter()

    # Pre-load sequentially: concurrent first loads would race on the download
    # and a permanently broken model is recorded as an abstention up-front.
    runnable: List[str] = []
    load_errors: Dict[str, str] = {}
    for model_id in selected:
        try:
            load_model(model_id)
            runnable.append(model_id)
        except Exception as exc:  # noqa: BLE001 - degrade to the healthy models
            logger.error("Model '%s' unavailable, excluded from the vote: %s", model_id, exc)
            load_errors[model_id] = str(exc)

    if not runnable:
        raise RuntimeError(f"No selected model could be loaded: {'; '.join(load_errors.values())}")

    if len(runnable) > 1 and settings.ml_parallel and resolve_device() == -1:
        with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
            outcomes = list(pool.map(lambda mid: _predict_one(mid, image, k), runnable))
    else:
        outcomes = [_predict_one(mid, image, k) for mid in runnable]

    failed = [o for o in outcomes if not o["ok"]]
    ok = [o for o in outcomes if o["ok"]]
    if not ok:
        details = "; ".join(f"{o['id']}: {o['error']}" for o in failed)
        raise RuntimeError(f"All selected models failed: {details}")

    winner = _hard_vote(ok)
    top_label = winner["label"]
    top_score = winner["score"]
    agreement = winner["agreement"]
    voting = len(selected) > 1
    confident = bool(ok) and top_score >= settings.ml_confidence_floor
    healthy = is_healthy_label(top_label)

    if not any(o["detections"] for o in ok):
        status = "unknown"
    elif not confident:
        status = "uncertain"
    elif healthy:
        status = "healthy"
    else:
        status = "diseased"

    votes: List[Dict[str, Any]] = []
    for model_id in selected:
        outcome = next((o for o in outcomes if o["id"] == model_id), None)
        if outcome is None:
            votes.append(
                {
                    "model": model_id,
                    "model_label": MODEL_REGISTRY[model_id]["label"],
                    "label": None,
                    "raw_label": None,
                    "score": None,
                    "ms": None,
                    "ok": False,
                    "error": load_errors.get(model_id, "not loaded"),
                }
            )
        else:
            votes.append(
                {
                    "model": model_id,
                    "model_label": outcome["label"],
                    "label": outcome["top_label"] if outcome["ok"] else None,
                    "raw_label": outcome["detections"][0]["raw_label"] if outcome["ok"] and outcome["detections"] else None,
                    "score": outcome["top_score"] if outcome["ok"] else None,
                    "ms": outcome["ms"],
                    "ok": outcome["ok"],
                    "error": outcome["error"],
                }
            )

    inference_ms = round((time.perf_counter() - started) * 1000, 1)
    if voting:
        caption = f"{top_label} - {top_score}% ({winner['votes']}/{len(ok)} votes)"
    else:
        caption = f"{top_label} - {top_score}%"

    return {
        "detections": _merge_detections(ok, k),
        "status": status,
        "top_label": top_label,
        "top_score": top_score,
        "is_healthy": healthy,
        "severity": "None" if healthy else severity_from_label(top_label),
        "confident": confident,
        "confidence_floor": settings.ml_confidence_floor,
        "requires_expert_review": not confident,
        "inference_ms": inference_ms,
        "device": _model_device,
        "annotation_type": "prediction_caption",
        "annotated_image_base64": _annotate(image, caption),
        "mode": "voting" if voting else "single",
        "models": [{"id": m, "label": MODEL_REGISTRY[m]["label"]} for m in selected],
        "votes": votes,
        "agreement": agreement if voting else 100.0,
    }
