import os
import sys

# Monkeypatch sys.stderr.flush to prevent OSError: [Errno 22] Invalid argument on Windows
if hasattr(sys.stderr, "flush"):
    original_flush = sys.stderr.flush
    def safe_flush():
        try:
            original_flush()
        except OSError:
            pass
    sys.stderr.flush = safe_flush

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

from transformers import pipeline
from transformers.utils import logging
logging.disable_progress_bar()

from PIL import Image, ImageDraw
import io
import base64

detector = None

def load_or_download_model():
    global detector
    print("Loading Plant Disease Detection Model...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, "models", "plant_disease_model")
    
    detector = pipeline(
        "image-classification",
        model=model_path
    )
    print("Model Loaded Successfully!")

def predict_image(image_bytes: bytes):
    if detector is None:
        load_or_download_model()
        
    image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    
    results = detector(image)
    
    detections = []
    
    for result in results:
        label = result["label"]
        score = round(result["score"] * 100, 2)
        
        detections.append({
            "label": label,
            "score": score,
            "box": None
        })
        
    # Sort detections by score descending
    detections = sorted(detections, key=lambda x: x["score"], reverse=True)
    
    # Return original image if no bounding boxes to draw
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return {
        "detections": detections,
        "annotated_image_base64": img_str
    }

