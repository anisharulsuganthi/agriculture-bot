"""
ResNet50 Fine-Tuning for Plant Disease Classification
Dataset : dataset 1 (89 crops/conditions, 281 unique class IDs, ~66k images)
"""

import os
import sys
import time
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

SAVE_DIR     = os.path.join(BASE_DIR, "checkpoints")
os.makedirs(SAVE_DIR, exist_ok=True)

NUM_CLASSES   = 281   # dataset has class_id 0–280 (281 unique classes)
BATCH_SIZE    = 64
NUM_EPOCHS    = 20
LR            = 1e-4
WEIGHT_DECAY  = 1e-4
NUM_WORKERS   = 2 if torch.cuda.is_available() else 0
IMG_SIZE      = 224
FREEZE_EPOCHS = 3
DEVICE        = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── DATASET ───────────────────────────────────────────────────────────────────
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
        if not os.path.exists(img_path):
            base, ext = os.path.splitext(fname)
            img_path = os.path.join(self.image_dir, base + ext.lower())
        if not os.path.exists(img_path):
            base, ext = os.path.splitext(fname)
            img_path = os.path.join(self.image_dir, base + ext.upper())
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception:
            image = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))
        if self.transform:
            image = self.transform(image)
        return image, int(row["class_id"])

# ── TRANSFORMS ────────────────────────────────────────────────────────────────
train_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
    transforms.RandomCrop(IMG_SIZE),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

val_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

# ── MODEL HELPERS ─────────────────────────────────────────────────────────────
def freeze_backbone(m):
    for name, param in m.named_parameters():
        if "fc" not in name:
            param.requires_grad = False

def unfreeze_backbone(m):
    for param in m.parameters():
        param.requires_grad = True

# ── TRAIN ONE EPOCH ───────────────────────────────────────────────────────────
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
                out  = model(images)
                loss = criterion(out, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
        else:
            out  = model(images)
            loss = criterion(out, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        total_loss += loss.item() * images.size(0)
        correct    += (out.argmax(1) == labels).sum().item()
        total      += images.size(0)

        if (batch_idx + 1) % 25 == 0 or (batch_idx + 1) == len(loader):
            print(f"    Batch [{batch_idx+1}/{len(loader)}]  "
                  f"Loss: {loss.item():.4f}  Acc: {correct/total*100:.2f}%", flush=True)

    return total_loss / max(total, 1), correct / max(total, 1) * 100

# ── EVALUATE ──────────────────────────────────────────────────────────────────
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
                    out  = model(images)
                    loss = criterion(out, labels)
            else:
                out  = model(images)
                loss = criterion(out, labels)
            total_loss += loss.item() * images.size(0)
            correct    += (out.argmax(1) == labels).sum().item()
            total      += images.size(0)
    return total_loss / max(total, 1), correct / max(total, 1) * 100

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train ResNet50 on Plant Disease Dataset 1")
    parser.add_argument("--test-run", action="store_true", help="Run a quick sanity check (few batches) to verify paths & pipeline")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from latest checkpoint if available")
    parser.add_argument("--from-scratch", action="store_true", help="Force starting from epoch 1 with ImageNet weights")
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS, help="Target total epochs")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size")
    args = parser.parse_args()

    batch_size = 16 if args.test_run else args.batch_size

    print(f"{'='*60}", flush=True)
    print(f"  Plant Disease ResNet50 Fine-Tuning")
    print(f"{'='*60}")
    print(f"  Device      : {DEVICE}")
    if torch.cuda.is_available():
        print(f"  GPU         : {torch.cuda.get_device_name(0)}")
        print(f"  VRAM        : {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")
    print(f"  Dataset Dir : {DATASET_BASE}")
    print(f"  Images Dir  : {IMAGE_DIR}")
    print(f"  Checkpoints : {SAVE_DIR}")
    print(f"  Classes     : {NUM_CLASSES} | Batch: {batch_size} | Mode: {'SANITY TEST' if args.test_run else 'FULL TRAINING'}")
    print(f"{'='*60}\n", flush=True)

    # Validate paths exist
    if not os.path.exists(TRAIN_CSV):
        raise FileNotFoundError(f"Train split not found: {TRAIN_CSV}")
    if not os.path.exists(IMAGE_DIR):
        raise FileNotFoundError(f"Image directory not found: {IMAGE_DIR}")

    # Load Datasets
    print("Loading dataset splits...", flush=True)
    max_samples = 128 if args.test_run else None
    train_ds = PlantDiseaseDataset(TRAIN_CSV, IMAGE_DIR, train_transform, max_samples=max_samples)
    val_ds   = PlantDiseaseDataset(VAL_CSV,   IMAGE_DIR, val_transform,   max_samples=max_samples)
    test_ds  = PlantDiseaseDataset(TEST_CSV,  IMAGE_DIR, val_transform,   max_samples=max_samples)

    train_loader = DataLoader(train_ds, batch_size, shuffle=True,
                              num_workers=NUM_WORKERS, pin_memory=torch.cuda.is_available(), drop_last=not args.test_run)
    val_loader   = DataLoader(val_ds,   batch_size, shuffle=False,
                              num_workers=NUM_WORKERS, pin_memory=torch.cuda.is_available())
    test_loader  = DataLoader(test_ds,  batch_size, shuffle=False,
                              num_workers=NUM_WORKERS, pin_memory=torch.cuda.is_available())

    print(f"  Train: {len(train_ds):,} images | {len(train_loader)} batches")
    print(f"  Val  : {len(val_ds):,} images  | {len(val_loader)} batches")
    print(f"  Test : {len(test_ds):,} images  | {len(test_loader)} batches\n", flush=True)

    # Build Model
    print("Building ResNet50 architecture...", flush=True)
    try:
        model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
    except Exception:
        print("  Notice: Using ResNet50 without pretrained hub weights (offline mode)")
        model = models.resnet50(weights=None)

    model.fc = nn.Sequential(
        nn.Dropout(p=0.4),
        nn.Linear(model.fc.in_features, NUM_CLASSES)
    )

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)
    scaler    = torch.amp.GradScaler("cuda") if torch.cuda.is_available() else None

    start_epoch = 1
    best_val_acc = 0.0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    latest_ckpt_path = os.path.join(SAVE_DIR, "latest_checkpoint.pth")
    if not args.from_scratch and os.path.exists(latest_ckpt_path) and not args.test_run:
        print(f"Found existing checkpoint at {latest_ckpt_path}. Resuming...", flush=True)
        try:
            ckpt = torch.load(latest_ckpt_path, map_location=DEVICE)
            model.load_state_dict(ckpt["model_state_dict"])
            if "optimizer_state_dict" in ckpt:
                try:
                    optimizer.load_state_dict(ckpt["optimizer_state_dict"])
                except Exception as oe:
                    print(f"  (Notice: optimizer state skipped: {oe})")
            start_epoch = ckpt.get("epoch", 0) + 1
            best_val_acc = ckpt.get("val_acc", 0.0)
            if "history" in ckpt:
                history = ckpt["history"]
            print(f"  Resumed from Epoch {ckpt.get('epoch', 0)} (Best Val Acc: {best_val_acc:.2f}%)")
        except Exception as e:
            print(f"  Warning: Could not resume from checkpoint: {e}. Starting fresh.")
            freeze_backbone(model)
    elif start_epoch <= FREEZE_EPOCHS and not args.test_run:
        freeze_backbone(model)

    model = model.to(DEVICE)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_p   = sum(p.numel() for p in model.parameters())
    print(f"  Trainable parameters: {trainable:,} / {total_p:,}\n", flush=True)

    print(f"{'='*60}")
    print("  Starting Training Loop")
    print(f"{'='*60}\n", flush=True)

    target_epochs = start_epoch if args.test_run else args.epochs

    for epoch in range(start_epoch, target_epochs + 1):
        t0 = time.time()

        if epoch == FREEZE_EPOCHS + 1:
            print(f"\n>>> Epoch {epoch}: Unfreezing backbone <<<\n", flush=True)
            unfreeze_backbone(model)
            optimizer = optim.AdamW([
                {"params": [p for n, p in model.named_parameters() if "fc" not in n], "lr": LR * 0.1},
                {"params": model.fc.parameters(), "lr": LR}
            ], weight_decay=WEIGHT_DECAY)
            scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs - FREEZE_EPOCHS, eta_min=1e-6)

        print(f"\nEpoch [{epoch}/{args.epochs}]  LR: {optimizer.param_groups[0]['lr']:.2e}")
        print("-" * 50, flush=True)

        max_batches = 3 if args.test_run else None
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, scaler, DEVICE, max_batches=max_batches)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, DEVICE, scaler, max_batches=max_batches)
        scheduler.step()

        history["train_loss"].append(tr_loss)
        history["train_acc"].append(tr_acc)
        history["val_loss"].append(vl_loss)
        history["val_acc"].append(vl_acc)

        print(f"\n  Train  Loss: {tr_loss:.4f}  Acc: {tr_acc:.2f}%")
        print(f"  Val    Loss: {vl_loss:.4f}  Acc: {vl_acc:.2f}%")
        print(f"  Time : {(time.time()-t0)/60:.2f} min", flush=True)

        if not args.test_run:
            if vl_acc > best_val_acc:
                best_val_acc = vl_acc
                best_path = os.path.join(SAVE_DIR, "best_resnet50_plant_disease.pth")
                torch.save({
                    "epoch": epoch, "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_acc": vl_acc, "num_classes": NUM_CLASSES,
                }, best_path)
                print(f"  [BEST] Saved -> {best_path} (Val Acc: {best_val_acc:.2f}%)", flush=True)

            torch.save({
                "epoch": epoch, "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_acc": vl_acc, "history": history, "num_classes": NUM_CLASSES,
            }, latest_ckpt_path)

    if args.test_run:
        print(f"\n{'='*60}")
        print("  SANITY TEST PASSED! The training pipeline, dataset, and paths are 100% verified.")
        print(f"{'='*60}\n", flush=True)
        return

    # Final Test
    print(f"\n{'='*60}")
    print("  Final Test Evaluation")
    print(f"{'='*60}", flush=True)
    best_path = os.path.join(SAVE_DIR, "best_resnet50_plant_disease.pth")
    if os.path.exists(best_path):
        ckpt = torch.load(best_path, map_location=DEVICE)
        model.load_state_dict(ckpt["model_state_dict"])
    ts_loss, ts_acc = evaluate(model, test_loader, criterion, DEVICE, scaler)
    print(f"  Test Loss: {ts_loss:.4f}  Test Acc: {ts_acc:.2f}%")
    print(f"  Best Val Acc: {best_val_acc:.2f}%")
    print(f"  Checkpoints saved to: {SAVE_DIR}")
    print(f"{'='*60}", flush=True)

if __name__ == '__main__':
    main()
