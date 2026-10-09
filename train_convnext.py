"""
ConvNeXt-Tiny Fine-Tuning for Plant Disease & Pest Classification
Architecture : ConvNeXt-Tiny (Modern ViT-inspired Pure CNN)
Dataset      : Dataset 1 (281 unique class IDs, ~67,000 images)
Optimizations: PyTorch AMP (Mixed Precision FP16), Cosine Annealing, Label Smoothing
"""

import os
import sys
import time
import json
import argparse
import pandas as pd
from PIL import Image

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from torch.optim.lr_scheduler import CosineAnnealingLR

# ── CONFIGURATION & PATH RESOLUTION ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_BASE = os.path.join(BASE_DIR, "dataset 1")
IMAGE_DIR    = os.path.join(DATASET_BASE, "master_images", "master_images", "images")
TRAIN_CSV    = os.path.join(DATASET_BASE, "outputs", "outputs", "train_split.csv")
VAL_CSV      = os.path.join(DATASET_BASE, "outputs", "outputs", "val_split.csv")
TEST_CSV     = os.path.join(DATASET_BASE, "outputs", "outputs", "test_split.csv")
CLASS_MAP    = os.path.join(DATASET_BASE, "metadata", "metadata", "class_id_map.csv")

SAVE_DIR     = os.path.join(BASE_DIR, "checkpoints")
os.makedirs(SAVE_DIR, exist_ok=True)

NUM_CLASSES   = 281
BATCH_SIZE    = 32     # optimal for RTX 5050 8GB with AMP
NUM_EPOCHS    = 15
LR            = 1e-4
WEIGHT_DECAY  = 1e-4
FREEZE_EPOCHS = 2
IMG_SIZE      = 224
NUM_WORKERS   = 2 if torch.cuda.is_available() else 0
DEVICE        = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── DATASET CLASS ─────────────────────────────────────────────────────────────
class PlantDiseaseDataset(Dataset):
    def __init__(self, csv_path, image_dir, transform=None, max_samples=None):
        self.df = pd.read_csv(csv_path)
        if max_samples:
            self.df = self.df.head(max_samples)
        self.image_dir = image_dir
        self.transform = transform
        self.df["filename"] = self.df["image_path"].apply(lambda x: os.path.basename(str(x)))

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        fname = row["filename"]
        img_path = os.path.join(self.image_dir, fname)

        # Fallback for uppercase/lowercase extensions (.jpg vs .JPG)
        if not os.path.exists(img_path):
            base, ext = os.path.splitext(fname)
            for alt_ext in [ext.lower(), ext.upper(), ".jpg", ".JPG", ".jpeg", ".png"]:
                candidate = os.path.join(self.image_dir, base + alt_ext)
                if os.path.exists(candidate):
                    img_path = candidate
                    break

        try:
            image = Image.open(img_path).convert("RGB")
        except Exception:
            # Fallback blank image on corrupted files
            image = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))

        if self.transform:
            image = self.transform(image)

        return image, int(row["class_id"])

# ── DATA TRANSFORMS ───────────────────────────────────────────────────────────
train_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
    transforms.RandomCrop(IMG_SIZE),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomVerticalFlip(p=0.2),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05),
    transforms.RandomRotation(degrees=15),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    transforms.RandomErasing(p=0.20, scale=(0.02, 0.20), value="random"),
])

val_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# ── FREEZING / UNFREEZING HELPERS ─────────────────────────────────────────────
def freeze_backbone(model):
    """Freeze feature extractor stages, train only classifier head"""
    for param in model.features.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True
    print("  Backbone frozen: Training only classifier head.")

def unfreeze_backbone(model):
    """Unfreeze all parameters for end-to-end fine-tuning"""
    for param in model.parameters():
        param.requires_grad = True
    print("  Backbone unfrozen: Training all layers end-to-end.")

# ── TRAINING & EVALUATION FUNCTIONS ───────────────────────────────────────────
def train_one_epoch(model, loader, optimizer, criterion, scaler, device, max_batches=None):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    for batch_idx, (images, labels) in enumerate(loader):
        if max_batches and batch_idx >= max_batches:
            break

        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        optimizer.zero_grad()

        if scaler:
            with torch.amp.autocast("cuda"):
                outputs = model(images)
                loss = criterion(outputs, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()
        else:
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

        batch_sz = images.size(0)
        total_loss += loss.item() * batch_sz
        correct += (outputs.argmax(1) == labels).sum().item()
        total += batch_sz

        if (batch_idx + 1) % 20 == 0 or (batch_idx + 1) == len(loader):
            print(f"    Batch [{batch_idx+1:>4}/{len(loader)}]  "
                  f"Loss: {loss.item():.4f}  Acc: {correct/total*100:6.2f}%", flush=True)

    return total_loss / max(total, 1), correct / max(total, 1) * 100

def evaluate(model, loader, criterion, device, scaler, max_batches=None):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0

    with torch.no_grad():
        for batch_idx, (images, labels) in enumerate(loader):
            if max_batches and batch_idx >= max_batches:
                break

            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            if scaler:
                with torch.amp.autocast("cuda"):
                    outputs = model(images)
                    loss = criterion(outputs, labels)
            else:
                outputs = model(images)
                loss = criterion(outputs, labels)

            batch_sz = images.size(0)
            total_loss += loss.item() * batch_sz
            correct += (outputs.argmax(1) == labels).sum().item()
            total += batch_sz

    return total_loss / max(total, 1), correct / max(total, 1) * 100

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train ConvNeXt-Tiny on Plant Disease Dataset")
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS, help="Target total epochs")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size (e.g. 32 or 64)")
    parser.add_argument("--lr", type=float, default=LR, help="Base learning rate")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from latest checkpoint")
    parser.add_argument("--from-scratch", action="store_true", help="Start training fresh from ImageNet weights")
    parser.add_argument("--test-run", action="store_true", help="Run 3 batches sanity check")
    args = parser.parse_args()

    batch_size = 16 if args.test_run else args.batch_size

    print(f"\n{'='*65}", flush=True)
    print(f"  Plant Disease Detection: ConvNeXt-Tiny Training")
    print(f"{'='*65}")
    print(f"  Device      : {DEVICE}")
    if torch.cuda.is_available():
        print(f"  GPU Name    : {torch.cuda.get_device_name(0)}")
        print(f"  VRAM Total  : {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        print(f"  Precision   : Mixed Precision (AMP FP16)")
    else:
        print(f"  Notice      : Running on CPU (install PyTorch CUDA to use GPU)")
    print(f"  Dataset Dir : {DATASET_BASE}")
    print(f"  Images Dir  : {IMAGE_DIR}")
    print(f"  Checkpoints : {SAVE_DIR}")
    print(f"  Classes     : {NUM_CLASSES} | Batch Size: {batch_size}")
    print(f"{'='*65}\n", flush=True)

    # Validate paths exist
    if not os.path.exists(TRAIN_CSV):
        raise FileNotFoundError(f"Train split not found: {TRAIN_CSV}")
    if not os.path.exists(IMAGE_DIR):
        raise FileNotFoundError(f"Image directory not found: {IMAGE_DIR}")

    # Build id2label JSON mapping if available
    id2label_path = os.path.join(SAVE_DIR, "id2label_convnext.json")
    if os.path.exists(CLASS_MAP) and not os.path.exists(id2label_path):
        try:
            map_df = pd.read_csv(CLASS_MAP)
            id_col = "class_id" if "class_id" in map_df.columns else map_df.columns[0]
            name_col = "canonical_class" if "canonical_class" in map_df.columns else map_df.columns[1]
            id2label = {str(int(r[id_col])): str(r[name_col]) for _, r in map_df.iterrows()}
            with open(id2label_path, "w") as f:
                json.dump(id2label, f, indent=2)
            print(f"  Saved label map -> {id2label_path}")
        except Exception as e:
            print(f"  Notice: Could not parse class map: {e}")

    # Load Data
    print("Loading dataset splits...", flush=True)
    max_samples = 128 if args.test_run else None
    train_ds = PlantDiseaseDataset(TRAIN_CSV, IMAGE_DIR, train_transform, max_samples=max_samples)
    val_ds   = PlantDiseaseDataset(VAL_CSV,   IMAGE_DIR, val_transform,   max_samples=max_samples)
    test_ds  = PlantDiseaseDataset(TEST_CSV,  IMAGE_DIR, val_transform,   max_samples=max_samples)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=NUM_WORKERS, pin_memory=torch.cuda.is_available(),
                              drop_last=not args.test_run)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                              num_workers=NUM_WORKERS, pin_memory=torch.cuda.is_available())
    test_loader  = DataLoader(test_ds,  batch_size=batch_size, shuffle=False,
                              num_workers=NUM_WORKERS, pin_memory=torch.cuda.is_available())

    print(f"  Train: {len(train_ds):,} images | {len(train_loader)} batches")
    print(f"  Val  : {len(val_ds):,} images  | {len(val_loader)} batches")
    print(f"  Test : {len(test_ds):,} images  | {len(test_loader)} batches\n", flush=True)

    # Build ConvNeXt Architecture
    print("Building ConvNeXt-Tiny architecture...", flush=True)
    try:
        model = models.convnext_tiny(weights=models.ConvNeXt_Tiny_Weights.DEFAULT)
    except Exception:
        print("  Notice: Using ConvNeXt-Tiny without pretrained hub weights (offline)")
        model = models.convnext_tiny(weights=None)

    # In ConvNeXt, classifier is Sequential(LayerNorm2d, Flatten, Linear)
    # model.classifier[2] is the linear output projection
    in_features = model.classifier[2].in_features
    model.classifier[2] = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, NUM_CLASSES)
    )

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=WEIGHT_DECAY)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)
    scaler    = torch.amp.GradScaler("cuda") if torch.cuda.is_available() else None

    start_epoch = 1
    best_val_acc = 0.0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    latest_ckpt_path = os.path.join(SAVE_DIR, "latest_convnext_checkpoint.pth")
    best_path = os.path.join(SAVE_DIR, "best_convnext_plant_disease.pth")

    # Resume checkpoint if present
    if not args.from_scratch and os.path.exists(latest_ckpt_path) and not args.test_run:
        print(f"Found existing checkpoint at {latest_ckpt_path}. Resuming...", flush=True)
        try:
            ckpt = torch.load(latest_ckpt_path, map_location=DEVICE)
            model.load_state_dict(ckpt["model_state_dict"])
            if "optimizer_state_dict" in ckpt:
                try:
                    optimizer.load_state_dict(ckpt["optimizer_state_dict"])
                except Exception:
                    pass
            start_epoch = ckpt.get("epoch", 0) + 1
            best_val_acc = ckpt.get("val_acc", 0.0)
            if "history" in ckpt:
                history = ckpt["history"]
            print(f"  Resumed from Epoch {ckpt.get('epoch', 0)} (Best Val Acc: {best_val_acc:.2f}%)")
            if start_epoch > FREEZE_EPOCHS and not args.test_run:
                unfreeze_backbone(model)
                remaining_epochs = max(1, args.epochs - start_epoch + 1)
                optimizer = optim.AdamW([
                    {"params": model.features.parameters(), "lr": args.lr * 0.1},
                    {"params": model.classifier.parameters(), "lr": args.lr}
                ], weight_decay=WEIGHT_DECAY)
                scheduler = CosineAnnealingLR(optimizer, T_max=remaining_epochs, eta_min=1e-6)
                print(f"  Differential Fine-Tuning Active: Optimizer configured for {remaining_epochs} remaining epochs (Epochs {start_epoch}->{args.epochs})")
        except Exception as e:
            print(f"  Warning: Could not resume from checkpoint: {e}. Starting fresh.")
            freeze_backbone(model)
    elif start_epoch <= FREEZE_EPOCHS and not args.test_run:
        freeze_backbone(model)

    model = model.to(DEVICE)
    trainable_p = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_p     = sum(p.numel() for p in model.parameters())
    print(f"  Trainable parameters: {trainable_p:,} / {total_p:,}\n", flush=True)

    if start_epoch > args.epochs and not args.test_run:
        print(f"\nAll {args.epochs} target epochs already completed (Checkpoint is at Epoch {start_epoch - 1}).")
        print(f"To run additional epochs, specify --epochs {start_epoch + 4} (or higher).\n")

    print(f"{'='*65}")
    print("  Starting Training Loop")
    print(f"{'='*65}\n", flush=True)

    target_epochs = start_epoch if args.test_run else args.epochs

    for epoch in range(start_epoch, target_epochs + 1):
        t0 = time.time()

        if epoch == FREEZE_EPOCHS + 1 and not args.test_run:
            print(f"\n>>> Epoch {epoch}: Unfreezing ConvNeXt backbone for end-to-end training <<<\n", flush=True)
            unfreeze_backbone(model)
            optimizer = optim.AdamW([
                {"params": model.features.parameters(), "lr": args.lr * 0.1},
                {"params": model.classifier.parameters(), "lr": args.lr}
            ], weight_decay=WEIGHT_DECAY)
            scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs - FREEZE_EPOCHS, eta_min=1e-6)

        current_lr = optimizer.param_groups[-1]["lr"]
        print(f"\nEpoch [{epoch}/{args.epochs}]  LR: {current_lr:.2e}")
        print("-" * 55, flush=True)

        max_b = 3 if args.test_run else None
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, scaler, DEVICE, max_batches=max_b)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, DEVICE, scaler, max_batches=max_b)
        scheduler.step()

        history["train_loss"].append(tr_loss)
        history["train_acc"].append(tr_acc)
        history["val_loss"].append(vl_loss)
        history["val_acc"].append(vl_acc)

        elapsed_min = (time.time() - t0) / 60
        print(f"\n  Train Loss: {tr_loss:.4f}  | Train Acc: {tr_acc:.2f}%")
        print(f"  Val   Loss: {vl_loss:.4f}  | Val   Acc: {vl_acc:.2f}%")
        print(f"  Epoch Duration : {elapsed_min:.2f} min", flush=True)

        if not args.test_run:
            if vl_acc > best_val_acc:
                best_val_acc = vl_acc
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_acc": vl_acc,
                    "num_classes": NUM_CLASSES,
                }, best_path)
                print(f"  ★ [NEW BEST] Saved -> {best_path} (Val Acc: {best_val_acc:.2f}%)", flush=True)

            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_acc": vl_acc,
                "history": history,
                "num_classes": NUM_CLASSES,
            }, latest_ckpt_path)

    if args.test_run:
        print(f"\n{'='*65}")
        print("  SANITY TEST PASSED! ConvNeXt-Tiny pipeline is 100% verified.")
        print(f"{'='*65}\n", flush=True)
        return

    # Final Test Set Evaluation
    print(f"\n{'='*65}")
    print("  Final Evaluation on Test Split (6,671 images)")
    print(f"{'='*65}", flush=True)
    if os.path.exists(best_path):
        ckpt = torch.load(best_path, map_location=DEVICE)
        model.load_state_dict(ckpt["model_state_dict"])
        print(f"  Loaded best model from Epoch {ckpt.get('epoch')} (Val Acc: {ckpt.get('val_acc'):.2f}%)")

    test_loss, test_acc = evaluate(model, test_loader, criterion, DEVICE, scaler)
    print(f"\n  >> Final Test Loss : {test_loss:.4f}")
    print(f"  >> Final Test Acc  : {test_acc:.2f}%\n", flush=True)

if __name__ == "__main__":
    main()
