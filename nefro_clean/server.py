import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

try:
    from nefro_clean.predict import evaluate_patient
except ImportError:
    from predict import evaluate_patient

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
    html_path = os.path.join(current_dir, "index.html")
    if not os.path.exists(html_path):
        html_path = os.path.join(root_dir, "src", "clean_index.html")
    return FileResponse(html_path)


@app.post("/predict")
def predict_endpoint(patient: PatientInput):
    patient_dict = patient.dict()
    return evaluate_patient(patient_dict)


if __name__ == "__main__":
    print("=" * 70)
    print(" Starting NEFROAI-CLEAN Clinical Decision Support Server")
    print(" URL: http://127.0.0.1:8080/")
    print(" Press Ctrl+C in this terminal to stop.")
    print("=" * 70)
    uvicorn.run(app, host="127.0.0.1", port=8080)
