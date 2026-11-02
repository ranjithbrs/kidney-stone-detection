from ultralytics import YOLO
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "datasets"
DATA_YAML = DATASET_DIR / "data.yaml"

print("Project:", BASE_DIR)
print("Dataset:", DATASET_DIR)
print("YAML:", DATA_YAML)

model = YOLO("yolo11n.pt")

model.train(
    data=str(DATA_YAML),
    epochs=20,
    imgsz=448,
    batch=4,
    workers=0
)