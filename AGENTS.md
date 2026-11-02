# Project Guidelines: Kidney Stone Detection System

## 1. Environment & Runtime
- **Python Version**: Python 3.10.x.
- **Virtual Environment**: Always use the project-local virtual environment located at `.venv/`.
  - Windows: `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe`
- **Dependency Management**:
  - Never install packages globally.
  - When new packages are added, update `requirements.txt` (`.venv\Scripts\python.exe -m pip freeze > requirements.txt`).

## 2. Machine Learning & Computer Vision (YOLO11)
- **Framework**: `ultralytics` YOLO11.
- **Model Files**:
  - Base nano model: `yolo11n.pt` or `models/yolo11n.pt`.
  - Trained best weights: `models/best.pt` or `runs/detect/kidney/weights/best.pt`.
- **Dataset Configuration**: `datasets/data.yaml` defines classes:
  - `0`: Stone
  - `1`: Normal
- **Inference & Processing**: When adding prediction routes or scripts, ensure images are loaded safely via OpenCV / PIL, passed through `YOLO(model_path)`, and predictions return confidence scores and bounding boxes.

## 3. Web Application (Flask) & Database
- **Framework**: Flask (entry point: `App.py`).
- **Templates**: Stored in `templates/` using Jinja2 inheritance and partials (`templates/menu/`).
- **Static Files**: Stored in `static/` (CSS, JS, images, audio).
- **Database**:
  - Host: `localhost:3306`
  - Engine: MySQL (`mysql.connector`)
  - Database Name: `1kidneystoneyolodb`
  - Primary Tables: `regtb` (User registration & auth).
  - Connections must always be committed (`conn.commit()`) and properly closed in try/finally or context blocks.

## 4. Git & Repository Standards
- Do NOT commit `.venv/`, temporary caches (`__pycache__`), raw datasets in cache, or large model weight archives (`.pt`).
- Write descriptive, clean commit messages.
