# Kidney Stone Detection System (YOLO11 & Flask)

An end-to-end computer vision and web-based healthcare diagnostic platform designed to detect and localize kidney stones from medical images (CT scans / X-rays) using **Ultralytics YOLO11** paired with a **Flask** web portal and **MySQL** database.

---

## Features
- **YOLO11 Object Detection**: Custom-trained YOLO11 nano model (`yolo11n.pt`) fine-tuned for high-accuracy kidney stone localization (`0: stone`, `1: normal`).
- **Web Application**: Flask backend with Jinja2 templates and responsive Bootstrap UI.
- **Role-Based Portals**:
  - **User/Patient Portal**: Registration, login, profile view, and diagnostic dashboard.
  - **Admin Portal**: Admin authentication and registered patient/user auditing.
- **Alert System**: Built-in SMTP email alerts with detection image attachments and audio alerts.

---

## Project Structure
```
project/
├── .venv/                      # Python 3.10 virtual environment
├── database/                   # MySQL schema and database dumps
│   └── 1kidneystoneyolodb.sql
├── datasets/                   # Roboflow dataset for training & validation
│   ├── train/
│   ├── valid/
│   ├── test/
│   └── data.yaml
├── models/                     # YOLO model weights (yolo11n.pt, best.pt)
├── runs/                       # Model training checkpoints & performance curves
├── static/                     # CSS, JavaScript, vendor libraries & audio files
├── templates/                  # Flask HTML views (Admin, User, Auth, Navigation)
├── .gitignore                  # Git ignore rules
├── AGENTS.md                   # Antigravity project configuration & rules
├── App.py                      # Flask web application entrypoint
├── requirements.txt            # Pinned project dependencies
├── run.txt                     # YOLO training CLI command reference
├── trainyolo.py                # YOLO11 model training pipeline
└── README.md                   # Project documentation
```

---

## Tech Stack
- **Language**: Python 3.10
- **Computer Vision / Deep Learning**: Ultralytics YOLO11, PyTorch 2.5.1, OpenCV
- **Backend**: Flask 2.1.2, Werkzeug, Jinja2
- **Database**: MySQL (`mysql-connector-python`) / WampServer
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5, FontAwesome

---

## Setup & Installation

### 1. Prerequisites
- **Python 3.10**
- **MySQL / WampServer** (running on `localhost:3306`)

### 2. Environment Setup
```powershell
# Clone or open the project folder
cd "C:\Users\B Ranjith\Downloads\project"

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Verify installed dependencies
python -m pip install -r requirements.txt
```

### 3. Database Initialization
1. Start MySQL (e.g., via WampServer or standalone MySQL service).
2. Open phpMyAdmin or your MySQL client.
3. Import `database/1kidneystoneyolodb.sql` to create database `1kidneystoneyolodb` and the required tables (`regtb`).

### 4. Running the Application
```powershell
python App.py
```
Open your browser and navigate to:
```
http://localhost:5000
```
- **Admin Login**: Username `admin` / Password `admin`
- **User Portal**: Register a new account or log in with existing user credentials.

### 5. Training the YOLO Model
To re-train or fine-tune the model on custom images:
```powershell
python trainyolo.py
```
Model weights and evaluation metrics will be saved in `runs/detect/`.
