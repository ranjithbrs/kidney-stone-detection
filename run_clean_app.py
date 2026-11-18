"""
=============================================================================
NEFROAI-CLEAN: Simple Standalone Web Launcher
=============================================================================
Run with:
    .venv\\Scripts\\python.exe run_clean_app.py
Then open your browser at:
    http://127.0.0.1:8080/

This serves the clean, humanized clinical decision support system directly
overcoming all 5 limitations of the base paper.
=============================================================================
"""

import os
import sys

# Ensure src/ and project root are in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

from clean_predict import evaluate_patient

app = FastAPI(title="NEFROAI-CLEAN Clinical Decision Support API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PatientInput(BaseModel):
    age_years: float
    sex_code: int                            # 1 = Male, 2 = Female
    serum_glucose: float                     # Blood Sugar (mg/dL)
    blood_urea_nitrogen: float               # BUN (mg/dL)
    sodium: float                            # (mmol/L)
    potassium: float                         # (mmol/L)
    serum_creatinine: Optional[float] = None # Optional specialized renal lab (mg/dL)
    uacr: Optional[float] = None             # Optional urine ACR (mg/g)
    days_of_history: Optional[int] = 0       # Days between visits for chronicity check
    has_acute_spike: Optional[bool] = False  # Rapid creatinine rise flag (AKI)


@app.get("/")
def home():
    html_path = os.path.join(SRC_DIR, "clean_index.html")
    return FileResponse(html_path)


@app.post("/predict")
def predict_endpoint(patient: PatientInput):
    patient_dict = patient.dict()
    return evaluate_patient(patient_dict)


if __name__ == "__main__":
    print("=" * 70)
    print(" Starting NEFROAI-CLEAN Clinical Decision Support Web Server")
    print(" URL: http://127.0.0.1:8080/")
    print(" Press Ctrl+C in this terminal to stop.")
    print("=" * 70)
    uvicorn.run(app, host="127.0.0.1", port=8080)
