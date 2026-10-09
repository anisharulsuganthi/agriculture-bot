import os
import torch
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESNET_CKPT = os.path.join(BASE_DIR, "checkpoints", "latest_checkpoint.pth")
CONVNEXT_CKPT = os.path.join(BASE_DIR, "checkpoints", "latest_convnext_checkpoint.pth")
OUTPUT_DIRS = [
    os.path.join(BASE_DIR, "charts"),
    os.path.join(BASE_DIR, "agriculture-bot", "frontend", "images", "charts")
]

def generate_all_charts():
    for out_dir in OUTPUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)

    resnet_hist, convnext_hist = None, None

    if os.path.exists(RESNET_CKPT):
        try:
            ckpt = torch.load(RESNET_CKPT, map_location="cpu")
            resnet_hist = ckpt.get("history")
        except Exception as e:
            print(f"Error loading ResNet ckpt: {e}")

    if os.path.exists(CONVNEXT_CKPT):
        try:
            ckpt = torch.load(CONVNEXT_CKPT, map_location="cpu")
            convnext_hist = ckpt.get("history")
        except Exception as e:
            print(f"Error loading ConvNeXt ckpt: {e}")

    # 1. ResNet Loss & Acc
    if resnet_hist:
        epochs = range(1, len(resnet_hist["train_loss"]) + 1)
        # Loss
        plt.figure(figsize=(10, 6))
        plt.plot(epochs, resnet_hist["train_loss"], color='#1f77b4', marker='o', label='Training Loss', linewidth=2)
        plt.plot(epochs, resnet_hist["val_loss"], color='#d62728', marker='s', label='Validation Loss', linewidth=2)
        plt.title('Training and Validation Loss (ResNet-50)', fontsize=16, fontweight='bold')
        plt.xlabel('Epoch', fontsize=14)
        plt.ylabel('Cross-Entropy Loss', fontsize=14)
        plt.legend(fontsize=12, loc='upper right')
        plt.grid(True, linestyle='--', alpha=0.7)
        for out_dir in OUTPUT_DIRS:
            plt.savefig(os.path.join(out_dir, 'fig1_loss_curve.png'), dpi=300, bbox_inches='tight')
        plt.close()

        # Acc
        plt.figure(figsize=(10, 6))
        plt.plot(epochs, resnet_hist["train_acc"], color='#1f77b4', marker='o', label='Training Accuracy', linewidth=2)
        plt.plot(epochs, resnet_hist["val_acc"], color='#2ca02c', marker='s', label='Validation Accuracy', linewidth=2)
        plt.title('Training and Validation Accuracy (ResNet-50)', fontsize=16, fontweight='bold')
        plt.xlabel('Epoch', fontsize=14)
        plt.ylabel('Accuracy (%)', fontsize=14)
        plt.legend(fontsize=12, loc='lower right')
        plt.grid(True, linestyle='--', alpha=0.7)
        for out_dir in OUTPUT_DIRS:
            plt.savefig(os.path.join(out_dir, 'fig2_accuracy_curve.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("Generated ResNet figures (fig1, fig2).")

    # 2. ConvNeXt Loss & Acc
    if convnext_hist:
        epochs_cn = range(1, len(convnext_hist["train_loss"]) + 1)
        # Loss
        plt.figure(figsize=(10, 6))
        plt.plot(epochs_cn, convnext_hist["train_loss"], color='#9467bd', marker='o', label='Training Loss', linewidth=2)
        plt.plot(epochs_cn, convnext_hist["val_loss"], color='#e377c2', marker='s', label='Validation Loss', linewidth=2)
        plt.title('Training and Validation Loss (ConvNeXt-Tiny)', fontsize=16, fontweight='bold')
        plt.xlabel('Epoch', fontsize=14)
        plt.ylabel('Cross-Entropy Loss', fontsize=14)
        plt.legend(fontsize=12, loc='upper right')
        plt.grid(True, linestyle='--', alpha=0.7)
        for out_dir in OUTPUT_DIRS:
            plt.savefig(os.path.join(out_dir, 'fig3_convnext_loss_curve.png'), dpi=300, bbox_inches='tight')
        plt.close()

        # Acc
        plt.figure(figsize=(10, 6))
        plt.plot(epochs_cn, convnext_hist["train_acc"], color='#9467bd', marker='o', label='Training Accuracy', linewidth=2)
        plt.plot(epochs_cn, convnext_hist["val_acc"], color='#2ca02c', marker='s', label='Validation Accuracy', linewidth=2)
        plt.title('Training and Validation Accuracy (ConvNeXt-Tiny)', fontsize=16, fontweight='bold')
        plt.xlabel('Epoch', fontsize=14)
        plt.ylabel('Accuracy (%)', fontsize=14)
        plt.legend(fontsize=12, loc='lower right')
        plt.grid(True, linestyle='--', alpha=0.7)
        for out_dir in OUTPUT_DIRS:
            plt.savefig(os.path.join(out_dir, 'fig4_convnext_accuracy_curve.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("Generated ConvNeXt figures (fig3, fig4).")

    # 3. Head-to-Head Comparison Plot
    if resnet_hist and convnext_hist:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Comparison Val Accuracy
        ax1.plot(range(1, len(resnet_hist["val_acc"]) + 1), resnet_hist["val_acc"],
                 color='#1f77b4', marker='o', label=f'ResNet-50 (Max: {max(resnet_hist["val_acc"]):.2f}%)', linewidth=2)
        ax1.plot(range(1, len(convnext_hist["val_acc"]) + 1), convnext_hist["val_acc"],
                 color='#2ca02c', marker='^', label=f'ConvNeXt-Tiny (Max: {max(convnext_hist["val_acc"]):.2f}%)', linewidth=2.5)
        ax1.set_title('Validation Accuracy Comparison', fontsize=15, fontweight='bold')
        ax1.set_xlabel('Epoch', fontsize=13)
        ax1.set_ylabel('Validation Accuracy (%)', fontsize=13)
        ax1.legend(fontsize=11, loc='lower right')
        ax1.grid(True, linestyle='--', alpha=0.7)

        # Comparison Val Loss
        ax2.plot(range(1, len(resnet_hist["val_loss"]) + 1), resnet_hist["val_loss"],
                 color='#1f77b4', marker='o', label=f'ResNet-50 (Min: {min(resnet_hist["val_loss"]):.4f})', linewidth=2)
        ax2.plot(range(1, len(convnext_hist["val_loss"]) + 1), convnext_hist["val_loss"],
                 color='#e377c2', marker='^', label=f'ConvNeXt-Tiny (Min: {min(convnext_hist["val_loss"]):.4f})', linewidth=2.5)
        ax2.set_title('Validation Loss Comparison', fontsize=15, fontweight='bold')
        ax2.set_xlabel('Epoch', fontsize=13)
        ax2.set_ylabel('Validation Loss', fontsize=13)
        ax2.legend(fontsize=11, loc='upper right')
        ax2.grid(True, linestyle='--', alpha=0.7)

        plt.suptitle('ResNet-50 vs ConvNeXt-Tiny Empirical Training Benchmark', fontsize=17, fontweight='bold', y=1.02)
        for out_dir in OUTPUT_DIRS:
            plt.savefig(os.path.join(out_dir, 'fig5_resnet_vs_convnext_comparison.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("Generated Comparison figure (fig5).")

if __name__ == "__main__":
    generate_all_charts()
