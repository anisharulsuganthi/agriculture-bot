import os
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from tqdm import tqdm

# --- Configuration ---
DATASET_DIR = r"c:\Users\Anish\Music\plant detection model\dataset 1"
MANIFEST_PATH = os.path.join(DATASET_DIR, "metadata", "metadata", "dataset_manifest.csv")
IMAGES_BASE_DIR = os.path.join(DATASET_DIR, "master_images", "master_images")

BATCH_SIZE = 32
EPOCHS = 5
LEARNING_RATE = 1e-4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Using device: {DEVICE}")

# --- Dataset Class ---
class PlantDiseaseDataset(Dataset):
    def __init__(self, df, img_dir, transform=None):
        self.df = df
        self.img_dir = img_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # The manifest has paths like 'images/img_00000000.jpg'
        img_path = os.path.join(self.img_dir, row["image_path"])
        
        # Convert to RGB (in case of RGBA or Grayscale)
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"Error loading image {img_path}: {e}")
            # fallback to a blank image if one fails to load
            image = Image.new("RGB", (224, 224))
            
        label = row["label"]

        if self.transform:
            image = self.transform(image)

        return image, label

def main():
    print("Loading dataset manifest...")
    df = pd.read_csv(MANIFEST_PATH)
    
    # Check number of unique classes and map them to contiguous indices 0..N-1
    unique_classes = sorted(df["class_id"].unique())
    class_to_idx = {cls: idx for idx, cls in enumerate(unique_classes)}
    df["label"] = df["class_id"].map(class_to_idx)
    num_classes = len(unique_classes)
    print(f"Found {len(df)} images across {num_classes} classes.")
    
    # Stratified split requires at least 2 samples per class.
    # For classes with only 1 sample, keep them in the training set and stratify the rest.
    class_counts = df["label"].value_counts()
    single_sample_classes = class_counts[class_counts < 2].index
    
    df_single = df[df["label"].isin(single_sample_classes)]
    df_multi = df[~df["label"].isin(single_sample_classes)]
    
    train_multi, val_df = train_test_split(
        df_multi, test_size=0.2, random_state=42, stratify=df_multi["label"]
    )
    train_df = pd.concat([train_multi, df_single]).sample(frac=1, random_state=42).reset_index(drop=True)
    val_df = val_df.reset_index(drop=True)
    
    print(f"Training samples: {len(train_df)}, Validation samples: {len(val_df)}")
    
    # --- Data Augmentation & Transforms ---
    # To improve accuracy and prevent overfitting, we add random rotations, flips, etc.
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    train_dataset = PlantDiseaseDataset(train_df, IMAGES_BASE_DIR, transform=train_transform)
    val_dataset = PlantDiseaseDataset(val_df, IMAGES_BASE_DIR, transform=val_transform)
    
    # Set num_workers=0 on Windows to avoid multiprocessing issues initially
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    
    # --- Model Setup ---
    # Using MobileNet_V2 as it is lightweight and fast for fine-tuning
    print("Setting up MobileNet_V2 model...")
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    
    # Freeze early layers to retain feature extraction capabilities and train faster
    for param in model.parameters():
        param.requires_grad = False
        
    # Unfreeze the last few layers for fine-tuning
    for param in model.features[-4:].parameters():
        param.requires_grad = True

    # Modify the classifier head for our specific number of classes
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
    model = model.to(DEVICE)
    
    criterion = nn.CrossEntropyLoss()
    # Optimize only the parameters that require gradients
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=LEARNING_RATE)
    
    # --- Training Loop ---
    print("\nStarting Training...")
    best_f1 = 0.0
    
    for epoch in range(EPOCHS):
        model.train()
        running_loss = 0.0
        
        print(f"\nEpoch {epoch+1}/{EPOCHS}")
        for inputs, labels in tqdm(train_loader, desc="Training"):
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * inputs.size(0)
            
        epoch_loss = running_loss / len(train_dataset)
        
        # --- Validation Phase ---
        model.eval()
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for inputs, labels in tqdm(val_loader, desc="Validating"):
                inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
                outputs = model(inputs)
                _, preds = torch.max(outputs, 1)
                
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
                
        # Calculate Accuracy and F1 Score (weighted for class imbalances)
        acc = accuracy_score(all_labels, all_preds)
        f1 = f1_score(all_labels, all_preds, average='weighted')
        
        print(f"Train Loss: {epoch_loss:.4f}")
        print(f"Val Accuracy: {acc:.4f} ({acc*100:.2f}%)")
        print(f"Val F1 Score: {f1:.4f}")
        
        # Save the best model
        if f1 > best_f1:
            best_f1 = f1
            torch.save(model.state_dict(), "best_plant_model.pth")
            print(">>> Saved new best model! <<<")
            
    print("\nTraining Complete! Best model saved as 'best_plant_model.pth'")

if __name__ == "__main__":
    main()
