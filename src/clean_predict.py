"""
=============================================================================
NEFROAI-CLEAN: Complete Patient Evaluation & Decision Support
=============================================================================
Combines:
1. Routine Screening ML Model (Trained on CDC NHANES N=5,069)
2. KDIGO 2024 CGA Clinical Staging
3. 90-Day Chronicity & AKI Filter
4. Actionable Target Lab Goals (Counterfactual Recourse)
=============================================================================
"""

import pandas as pd
import joblib
import os
import sys

# Ensure current folder is in path for easy execution
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from nefro_clean.clinical_rules import (
        compute_ckdepi_egfr,
        get_kdigo_stage,
        check_chronicity_and_aki,
        get_actionable_target_goals,
    )
except ImportError:
    from clinical_rules import (
        compute_ckdepi_egfr,
        get_kdigo_stage,
        check_chronicity_and_aki,
        get_actionable_target_goals,
    )


def load_screening_model():
    """Loads the saved Random Forest model artifact."""
    model_path = os.path.join(current_dir, "nhanes_rf_model.pkl")
    if not os.path.exists(model_path):
        model_path = os.path.join(current_dir, "..", "models", "nhanes_rf_model.pkl")
    artifact = joblib.load(model_path)
    return artifact["model"], artifact["imputer"], artifact["feature_cols"]


def evaluate_patient(patient_data):
    """
    Takes patient data and returns a comprehensive clinical evaluation.
    """
    model, imputer, feature_cols = load_screening_model()

    # 1. SCREENING MODEL RISK PREDICTION
    patient_df = pd.DataFrame([patient_data])[feature_cols]
    patient_clean = imputer.transform(patient_df)
    risk_prob = float(model.predict_proba(patient_clean)[0][1])
    risk_pct = round(risk_prob * 100, 1)

    if risk_pct >= 50.0:
        risk_tier = "High Risk"
        recommendation = "HIGH RISK: Schedule confirmatory renal panel (eGFR & uACR) and nephrology review."
    elif risk_pct >= 35.0:
        risk_tier = "Moderate Risk"
        recommendation = "MODERATE RISK: Borderline indicators. Recheck metabolic labs in 3-6 months."
    else:
        risk_tier = "Low Risk"
        recommendation = "LOW RISK: Routine annual health checkup follow-up."

    # 2. OVERCOMING LIMITATION 3: KDIGO STAGING (If Creatinine is provided)
    egfr = None
    kdigo_g = "Creatinine not entered"
    kdigo_a = "uACR not entered"
    scr = patient_data.get("serum_creatinine")
    if scr is not None and scr != "" and float(scr) > 0:
        egfr = compute_ckdepi_egfr(scr, patient_data["age_years"], patient_data["sex_code"])
        kdigo_g, kdigo_a = get_kdigo_stage(egfr, patient_data.get("uacr"))

    # 3. OVERCOMING LIMITATION 4: CHRONICITY & AKI FILTER
    days_history = patient_data.get("days_of_history", 0)
    has_spike = patient_data.get("has_acute_spike", False)
    chronicity_note = check_chronicity_and_aki(days_history, has_spike)

    # 4. OVERCOMING LIMITATION 5: ACTIONABLE TARGET GOALS
    target_goals = get_actionable_target_goals(patient_data, risk_pct)

    return {
        "screening_risk_percentage": risk_pct,
        "risk_tier": risk_tier,
        "clinical_recommendation": recommendation,
        "egfr_ckdepi": egfr,
        "kdigo_filtration_stage": kdigo_g,
        "kdigo_albuminuria_stage": kdigo_a,
        "chronicity_status": chronicity_note,
        "actionable_target_goals": target_goals,
    }


# Quick test
if __name__ == "__main__":
    test_patient = {
        "age_years": 62,
        "sex_code": 1,
        "serum_glucose": 165,
        "blood_urea_nitrogen": 32,
        "sodium": 139,
        "potassium": 4.6,
        "serum_creatinine": 1.8, # mg/dL
        "uacr": 210,             # mg/g
        "days_of_history": 120   # Multi-visit history > 90 days
    }
    result = evaluate_patient(test_patient)
    print("=== Complete Patient Evaluation ===")
    for k, v in result.items():
        print(f"{k}: {v}")
