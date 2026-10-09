import os
import sys
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import models, transforms
from PIL import Image
import matplotlib.pyplot as plt

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_CLASSES = 281
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MODEL_WEIGHTS = os.path.join(BASE_DIR, "checkpoints", "best_resnet50_plant_disease.pth")
if not os.path.exists(MODEL_WEIGHTS):
    MODEL_WEIGHTS = os.path.join(BASE_DIR, "checkpoints", "latest_checkpoint.pth")

OUTPUT_DIRS = [
    os.path.join(BASE_DIR, "heatmaps"),
    os.path.join(BASE_DIR, "agriculture-bot", "frontend", "images", "charts")
]

# ── GRAD-CAM IMPLEMENTATION ───────────────────────────────────────────────────
class GradCAM:
    """
    Extracts the gradients and activations from a specific CNN layer
    to build a visual heatmap of what the model is looking at.
    """
    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        
        target_layer.register_forward_hook(self.save_activation)
        target_layer.register_full_backward_hook(self.save_gradient)

    def save_activation(self, module, input, output):
        self.activations = output

    def save_gradient(self, module, grad_input, grad_output):
        self.gradients = grad_output[0]

    def __call__(self, x, class_idx=None):
        self.model.eval()
        b, c, h, w = x.size()
        
        out = self.model(x)
        if class_idx is None:
            class_idx = out.argmax(dim=1).item()
            
        self.model.zero_grad()
        score = out[0, class_idx]
        score.backward()
        
        weights = torch.mean(self.gradients, dim=[2, 3], keepdim=True)
        cam = torch.sum(weights * self.activations, dim=1, keepdim=True)
        cam = F.relu(cam)
        
        cam = cam.squeeze().cpu().detach().numpy()
        cam = cv2.resize(cam, (w, h))
        cam = cam - np.min(cam)
        cam = cam / (np.max(cam) + 1e-8)
        return cam, class_idx


def generate_heatmap(image_path, model_path=MODEL_WEIGHTS, output_filename="paper_figure_1.png"):
    print(f"Generating Grad-CAM for {image_path}...")
    
    model = models.resnet50(weights=None)
    model.fc = torch.nn.Sequential(
        torch.nn.Dropout(p=0.4),
        torch.nn.Linear(model.fc.in_features, NUM_CLASSES)
    )
    
    if os.path.exists(model_path):
        ckpt = torch.load(model_path, map_location=DEVICE)
        state_dict = ckpt["model_state_dict"] if "model_state_dict" in ckpt else ckpt
        model.load_state_dict(state_dict)
        print(f"  -> Loaded weights from {model_path}")
    else:
        print(f"  -> WARNING: {model_path} not found.")
        return
        
    model = model.to(DEVICE)
    cam_extractor = GradCAM(model, model.layer4[-1])
    
    img_pil = Image.open(image_path).convert('RGB')
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    input_tensor = transform(img_pil).unsqueeze(0).to(DEVICE)
    
    cam, pred_class = cam_extractor(input_tensor)
    
    img_orig = np.array(img_pil.resize((224, 224)))
    heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    overlay = np.uint8(0.5 * img_orig + 0.5 * heatmap)
    
    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.imshow(img_orig)
    plt.title("Original Leaf")
    plt.axis('off')
    
    plt.subplot(1, 2, 2)
    plt.imshow(overlay)
    plt.title(f"AI Focus Area (Predicted Class: {pred_class})")
    plt.axis('off')
    
    for out_dir in OUTPUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, output_filename)
        plt.savefig(out_path, bbox_inches='tight', dpi=300)
        print(f"  -> Saved heatmap: {out_path}")
    plt.close()

if __name__ == '__main__':
    # Find first available test image in dataset 1
    sample_img = os.path.join(BASE_DIR, "dataset 1", "master_images", "master_images", "images", "img_00025856.JPG")
    if not os.path.exists(sample_img):
        # find any image
        img_dir = os.path.join(BASE_DIR, "dataset 1", "master_images", "master_images", "images")
        if os.path.exists(img_dir):
            files = os.listdir(img_dir)
            if files:
                sample_img = os.path.join(img_dir, files[0])

    if os.path.exists(sample_img):
        generate_heatmap(sample_img)
    else:
        print(f"Could not locate sample image at {sample_img}")
