import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_CHARTS = os.path.join(BASE_DIR, "charts")
SOURCE_HEATMAPS = os.path.join(BASE_DIR, "heatmaps")
DESTINATION = os.path.join(BASE_DIR, "agriculture-bot", "frontend", "images", "charts")

os.makedirs(DESTINATION, exist_ok=True)
print(f"Syncing charts to frontend: {DESTINATION}")

# Copy charts
if os.path.exists(SOURCE_CHARTS):
    for f in os.listdir(SOURCE_CHARTS):
        if f.endswith(".png"):
            src = os.path.join(SOURCE_CHARTS, f)
            dst = os.path.join(DESTINATION, f)
            shutil.copy2(src, dst)
            print(f"  -> Copied {f}")

# Copy heatmaps
if os.path.exists(SOURCE_HEATMAPS):
    for f in os.listdir(SOURCE_HEATMAPS):
        if f.endswith(".png"):
            src = os.path.join(SOURCE_HEATMAPS, f)
            dst = os.path.join(DESTINATION, f)
            shutil.copy2(src, dst)
            print(f"  -> Copied {f}")

print("Done! The UI (model_analytics.html) has the latest charts.")
