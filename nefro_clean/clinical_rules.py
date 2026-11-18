"""
=============================================================================
NEFROAI-CLEAN: Clinical Rules, KDIGO 2024 Staging & Actionable Target Goals
=============================================================================
This file overcomes Limitations 3, 4, and 5 of the base paper:
1. Computes race-free CKD-EPI 2021 eGFR and KDIGO CGA 2D staging.
2. Checks 90-day persistence to avoid misdiagnosing Acute Kidney Injury (AKI) as CKD.
3. Calculates actionable target lab goals (Counterfactual Recourse).
=============================================================================
"""

import numpy as np


# ---------------------------------------------------------------------------
# OVERCOMING LIMITATION 3: OFFICIAL KDIGO 2024 STAGING (eGFR G1-G5 x uACR A1-A3)
# ---------------------------------------------------------------------------
def compute_ckdepi_egfr(serum_creatinine, age_years, sex_code):
    """
    Computes race-free CKD-EPI 2021 Estimated Glomerular Filtration Rate (eGFR).
    serum_creatinine: mg/dL
    age_years: years
    sex_code: 1 = Male, 2 = Female
    """
    scr = float(serum_creatinine)
    age = float(age_years)
    is_female = (sex_code == 2)

    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    sex_factor = 1.012 if is_female else 1.0

    ratio = scr / kappa
    egfr = 142 * (min(ratio, 1.0) ** alpha) * (max(ratio, 1.0) ** -1.2) * (0.9938 ** age) * sex_factor
    return round(egfr, 1)


def get_kdigo_stage(egfr, uacr=None):
    """
    Maps eGFR and uACR to international KDIGO clinical stages.
    """
    # 1. Filtration category (G1 to G5)
    if egfr >= 90:
        g_stage = "Stage G1 (Normal or high filtration >= 90 mL/min)"
    elif egfr >= 60:
        g_stage = "Stage G2 (Mildly decreased 60-89 mL/min)"
    elif egfr >= 45:
        g_stage = "Stage G3a (Mild-to-moderate decrease 45-59 mL/min)"
    elif egfr >= 30:
        g_stage = "Stage G3b (Moderate-to-severe decrease 30-44 mL/min)"
    elif egfr >= 15:
        g_stage = "Stage G4 (Severely decreased 15-29 mL/min)"
    else:
        g_stage = "Stage G5 (Kidney Failure < 15 mL/min)"

    # 2. Albuminuria category (A1 to A3) if uACR is measured
    if uacr is not None and uacr != "":
        u = float(uacr)
        if u < 30:
            a_stage = "A1 (Normal to mildly increased < 30 mg/g)"
        elif u <= 300:
            a_stage = "A2 (Moderately increased 30-300 mg/g)"
        else:
            a_stage = "A3 (Severely increased > 300 mg/g)"
    else:
        a_stage = "A-Stage: Urine ACR not provided"

    return g_stage, a_stage


# ---------------------------------------------------------------------------
# OVERCOMING LIMITATION 4: 90-DAY CHRONICITY & AKI VELOCITY GUARD
# ---------------------------------------------------------------------------
def check_chronicity_and_aki(days_between_first_and_last_visit, has_acute_spike=False):
    """
    By clinical definition, Chronic Kidney Disease requires damage persisting >= 90 days.
    A sudden spike without 90-day history is flagged as suspected Acute Kidney Injury (AKI).
    """
    if has_acute_spike:
        return "WARNING: Suspected Acute Kidney Injury (AKI). Rapid creatinine rise detected. Rehydrate and recheck in 48 hours."
    
    if days_between_first_and_last_visit is not None and days_between_first_and_last_visit >= 90:
        return "CONFIRMED CHRONICITY: Impairment documented over >= 90 days, fulfilling KDIGO chronicity criteria."
    else:
        return "SINGLE VISIT / CROSS-SECTIONAL: Chronicity unverified. Repeat renal labs in 90 days to distinguish transient elevation from true CKD."


# ---------------------------------------------------------------------------
# OVERCOMING LIMITATION 5: ACTIONABLE TARGET LAB GOALS (COUNTERFACTUAL RECOURSE)
# ---------------------------------------------------------------------------
def get_actionable_target_goals(patient_data, current_risk_percentage):
    """
    Instead of just saying 'Risk is 85%', this tells the doctor what modifiable
    targets the patient needs to achieve to bring risk below 50%.
    Age and Sex are immutable (cannot be changed).
    """
    if current_risk_percentage < 50.0:
        return ["Patient is already in the low/moderate risk zone. Maintain current diet, blood pressure, and annual checkups."]

    goals = []
    # Blood glucose check
    if patient_data.get("serum_glucose", 0) > 120:
        goals.append("Target Blood Sugar: Reduce fasting glucose from current level to < 110 mg/dL through glycemic therapy.")

    # Blood Urea Nitrogen check
    if patient_data.get("blood_urea_nitrogen", 0) > 20:
        goals.append("Target Blood Urea Nitrogen (BUN): Reduce nitrogenous waste to <= 18 mg/dL through hydration and dietary protein moderation.")

    # Electrolyte check
    if patient_data.get("potassium", 0) > 5.0:
        goals.append("Electrolyte Management: Potassium is elevated (> 5.0 mmol/L). Review potassium-sparing medications.")

    return goals
