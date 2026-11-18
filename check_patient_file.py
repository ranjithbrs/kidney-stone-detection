"""
=============================================================================
NEFROAI-X: Standalone Clinical Patient File Evaluation Runner
=============================================================================
Allows clinicians, researchers, and viva evaluators to evaluate patient files
(Single-patient JSON or Cohort CSV) directly from the terminal or file upload
without manual typing.

Usage:
    .venv\\Scripts\\python.exe check_patient_file.py <path_to_file.json_or_csv>
    .venv\\Scripts\\python.exe check_patient_file.py sample_inputs/patient_1_healthy.json
    .venv\\Scripts\\python.exe check_patient_file.py sample_inputs/cohort_screening_batch.csv

If run without arguments, presents an interactive menu of sample input files.
=============================================================================
"""

import os
import sys
import json
import re
import argparse
import pandas as pd
import numpy as np

# Ensure project root and src/ are in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from src.clinical_rules import (
    compute_ckdepi_egfr,
    get_kdigo_stage,
    check_chronicity_and_aki,
    get_actionable_target_goals,
)
from nefro_clean.predict import evaluate_patient as evaluate_nhanes_patient


def _parse_clean_number(val, default=None, feat=""):
    """Robustly parse numbers and reconcile international SI lab units."""
    if val is None or pd.isna(val):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().lower()
    if s in ["", "?", "nan", "none", "null"]:
        return default

    # Unit conversions
    if feat in ["glucose", "bgr"]:
        if "mmol" in s:
            nums = re.findall(r"[-+]?\d*\.?\d+", s)
            return round(float(nums[0]) * 18.0182, 1) if nums else default
    elif feat in ["hemo"]:
        if "g/l" in s:
            nums = re.findall(r"[-+]?\d*\.?\d+", s)
            return round(float(nums[0]) / 10.0, 1) if nums else default
    elif feat in ["sc", "creatinine"]:
        if "umol" in s or "µmol" in s:
            nums = re.findall(r"[-+]?\d*\.?\d+", s)
            return round(float(nums[0]) / 88.42, 2) if nums else default

    nums = re.findall(r"[-+]?\d*\.?\d+", s)
    if nums:
        return float(nums[0])
    return default


def evaluate_single_patient_dict(p: dict) -> dict:
    """
    Evaluates a single patient record across all 4 clinical engines:
    1. Routine Screening ML Model (CDC NHANES N=5,069)
    2. Official KDIGO 2024 CGA eGFR Staging (2021 CKD-EPI race-free)
    3. 90-Day Chronicity & AKI Filter (rules out acute dehydration spikes)
    4. Actionable Target Lab Goals (Counterfactual Recourse)
    """
    # Normalize keys
    age = _parse_clean_number(p.get("age_years", p.get("age")), default=50.0)
    sex_raw = str(p.get("sex", p.get("sex_code", "male"))).lower()
    sex_code = 2 if sex_raw in ["2", "female", "f"] else 1
    sex_str = "Female" if sex_code == 2 else "Male"

    # Routine screening labs with auto unit reconciliation
    glucose = _parse_clean_number(p.get("serum_glucose", p.get("bgr")), default=100.0, feat="glucose")
    bun = _parse_clean_number(p.get("blood_urea_nitrogen", p.get("bu")), default=18.0)
    sodium = _parse_clean_number(p.get("sodium", p.get("sod")), default=140.0)
    potassium = _parse_clean_number(p.get("potassium", p.get("pot")), default=4.5)

    # Specialized renal labs
    scr_val = p.get("serum_creatinine", p.get("sc"))
    scr_unit = str(p.get("serum_creatinine_unit", "mg/dL")).lower()
    if "umol" in scr_unit or "µmol" in scr_unit:
        scr_val = f"{scr_val} umol/L"
    scr_num = _parse_clean_number(scr_val, default=None, feat="sc")

    uacr_num = _parse_clean_number(p.get("uacr"), default=None)

    # Visit history
    days_history = int(_parse_clean_number(p.get("days_of_history"), default=0))
    has_spike = bool(p.get("has_acute_spike", False))
    # Clinical heuristic: if history is acute (<= 7 days) and creatinine is acutely elevated (>= 1.5 mg/dL), flag suspected AKI
    if not has_spike and 0 < days_history <= 7 and scr_num is not None and scr_num >= 1.5:
        has_spike = True

    # 1. Run Screening Model
    screen_input = {
        "age_years": age,
        "sex_code": sex_code,
        "serum_glucose": glucose,
        "blood_urea_nitrogen": bun,
        "sodium": sodium,
        "potassium": potassium,
        "serum_creatinine": scr_num,
        "uacr": uacr_num,
        "days_of_history": days_history,
        "has_acute_spike": has_spike,
    }
    screen_res = evaluate_nhanes_patient(screen_input)

    # 2. KDIGO Staging
    egfr = None
    kdigo_g = "Creatinine not measured"
    kdigo_a = "uACR not measured"
    if scr_num is not None and scr_num > 0:
        egfr = compute_ckdepi_egfr(scr_num, age, sex_code)
        kdigo_g, kdigo_a = get_kdigo_stage(egfr, uacr_num)

    # 3. Chronicity & AKI Filter
    chronicity_note = check_chronicity_and_aki(days_history, has_spike)

    # 4. Actionable Goals
    goals = get_actionable_target_goals(screen_input, screen_res["screening_risk_percentage"])

    return {
        "patient_id": p.get("patient_id", "PT-ANONYMOUS"),
        "name": p.get("name", "Clinical Patient"),
        "age": age,
        "sex": sex_str,
        "serum_creatinine_mg_dl": scr_num,
        "uacr_mg_g": uacr_num,
        "screening_risk_pct": screen_res["screening_risk_percentage"],
        "risk_tier": screen_res["risk_tier"],
        "clinical_recommendation": screen_res["clinical_recommendation"],
        "egfr_ckdepi": egfr,
        "kdigo_filtration_stage": kdigo_g,
        "kdigo_albuminuria_stage": kdigo_a,
        "chronicity_status": chronicity_note,
        "actionable_target_goals": goals,
    }


def print_single_report(res: dict):
    """Prints a beautiful, formatted terminal clinical report."""
    print("\n" + "=" * 80)
    print(f"       NEFROAI-X CLINICAL PATIENT EVALUATION REPORT")
    print("=" * 80)
    print(f" Patient ID:    {res['patient_id']:<25} Name: {res['name']}")
    print(f" Demographics:  Age {res['age']:.0f} | Biological Sex: {res['sex']}")
    print("-" * 80)

    # Risk badge
    tier = res["risk_tier"]
    score = res["screening_risk_pct"]
    print(f" SCREENING RISK SCORE:  {score:.1f}%  [{tier.upper()}]")
    print(f" Recommendation:        {res['clinical_recommendation']}")
    print("-" * 80)

    # KDIGO Staging
    print(" KDIGO 2024 CGA 2D STAGING & FILTRATION:")
    if res["egfr_ckdepi"] is not None:
        print(f"  • CKD-EPI 2021 eGFR:   {res['egfr_ckdepi']:.1f} mL/min/1.73m² (Race-neutral)")
    else:
        print(f"  • CKD-EPI 2021 eGFR:   Not Available (Creatinine not entered)")
    print(f"  • GFR Filtration:      {res['kdigo_filtration_stage']}")
    print(f"  • Albuminuria Grade:   {res['kdigo_albuminuria_stage']}")
    print("-" * 80)

    # 90-Day Chronicity
    print(" 90-DAY CHRONICITY & AKI FILTER (KDIGO Consensus Rule):")
    print(f"  • Status: {res['chronicity_status']}")
    print("-" * 80)

    # Actionable Goals
    print(" ACTIONABLE TARGET LAB GOALS (Counterfactual Recourse):")
    for goal in res["actionable_target_goals"]:
        print(f"  [✓] {goal}")
    print("=" * 80 + "\n")


def process_csv_file(filepath: str):
    """Processes a batch CSV patient file and outputs a clinical summary table and CSV."""
    print(f"\n[+] Loading batch patient cohort from: {filepath}")
    df = pd.read_csv(filepath)
    print(f"[+] Found {len(df)} patient records. Running clinical evaluation pipeline...\n")

    results = []
    for _, row in df.iterrows():
        p_dict = row.to_dict()
        res = evaluate_single_patient_dict(p_dict)
        results.append({
            "patient_id": res["patient_id"],
            "name": res["name"],
            "age": res["age"],
            "sex": res["sex"],
            "risk_score_pct": f"{res['screening_risk_pct']:.1f}%",
            "risk_tier": res["risk_tier"],
            "egfr": f"{res['egfr_ckdepi']:.1f}" if res["egfr_ckdepi"] is not None else "N/A",
            "kdigo_stage": f"{res['kdigo_filtration_stage'].split(':')[0]} · {res['kdigo_albuminuria_stage'].split(':')[0]}",
            "chronicity": "CONFIRMED CKD (>=90d)" if "confirmed chronicity" in res["chronicity_status"].lower() else (
                "SUSPECTED AKI" if "suspected acute" in res["chronicity_status"].lower() else "SINGLE VISIT"
            ),
        })

    out_df = pd.DataFrame(results)

    # Display clean table
    print("=" * 110)
    print(f"{'Patient ID':<12} | {'Name':<28} | {'Age/Sex':<9} | {'Risk %':<8} | {'Risk Tier':<12} | {'eGFR':<6} | {'KDIGO':<11} | {'Chronicity'}")
    print("-" * 110)
    for _, r in out_df.iterrows():
        print(f"{r['patient_id']:<12} | {r['name'][:28]:<28} | {str(int(r['age']))+'/'+r['sex'][0]:<9} | {r['risk_score_pct']:<8} | {r['risk_tier']:<12} | {r['egfr']:<6} | {r['kdigo_stage']:<11} | {r['chronicity']}")
    print("=" * 110)

    # Save output CSV to reports/
    os.makedirs(os.path.join(ROOT_DIR, "reports"), exist_ok=True)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    out_csv = os.path.join(ROOT_DIR, "reports", f"results_{base_name}.csv")
    out_df.to_csv(out_csv, index=False)
    print(f"\n[✓] Results successfully exported to: {out_csv}\n")


def interactive_menu():
    """Lists available sample input files for 1-click execution."""
    sample_dir = os.path.join(ROOT_DIR, "sample_inputs")
    sample_files = [
        ("patient_1_healthy.json", "Healthy Adult Checkup (Low Risk)"),
        ("patient_2_borderline.json", "Borderline Metabolic (Moderate Risk)"),
        ("patient_3_early_ckd.json", "Early Stage G3a A2 CKD"),
        ("patient_4_severe_ckd.json", "Advanced Stage G4 A3 CKD"),
        ("patient_5_suspected_aki.json", "Acute Dehydration / AKI Guard (4 Days History)"),
        ("cohort_screening_batch.csv", "10-Patient Cohort Batch File (CSV)"),
    ]

    print("\n" + "=" * 76)
    print("        NEFROAI-X: INPUT FILE CLINICAL EVALUATION RUNNER")
    print("=" * 76)
    print(" Select a sample input file to test, or enter a path to your own file:\n")
    for i, (fn, desc) in enumerate(sample_files, 1):
        print(f"  [{i}] {fn:<28} -> {desc}")
    print("\n  [Q] Quit")
    print("=" * 76)

    choice = input("\nEnter choice [1-6, Q, or custom file path]: ").strip()
    if choice.lower() in ["q", "exit", "quit", ""]:
        print("Exiting.")
        return

    if choice.isdigit() and 1 <= int(choice) <= len(sample_files):
        selected_file = os.path.join(sample_dir, sample_files[int(choice) - 1][0])
    else:
        selected_file = choice

    if not os.path.exists(selected_file):
        print(f"\n[!] File not found: {selected_file}")
        return

    run_on_file(selected_file)


def run_on_file(filepath: str):
    """Dispatches evaluation based on file extension (.json or .csv)."""
    if filepath.endswith(".json"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            print(f"\n[+] Found {len(data)} patient records in JSON list.")
            for item in data:
                res = evaluate_single_patient_dict(item)
                print_single_report(res)
        else:
            res = evaluate_single_patient_dict(data)
            print_single_report(res)
    elif filepath.endswith(".csv"):
        process_csv_file(filepath)
    else:
        print(f"[!] Unsupported file extension: {filepath}. Please provide .json or .csv")


def main():
    parser = argparse.ArgumentParser(description="Evaluate patient data from input files (.json / .csv).")
    parser.add_argument("file", nargs="?", default=None, help="Path to input .json or .csv patient file")
    args = parser.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"[!] File not found: {args.file}")
            sys.exit(1)
        run_on_file(args.file)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
