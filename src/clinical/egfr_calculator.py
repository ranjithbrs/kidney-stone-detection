"""NEFROAI-X Clinical Calculation Engine: Clinical eGFR Calculator.

Implements the official 2021 race-free CKD-EPI creatinine equation:
Reference:
    Inker LA, Eneanya ND, Coresh J, et al. New Creatinine- and Cystatin C-Based
    Equations to Estimate GFR without Race. N Engl J Med. 2021;385(19):1737-1749.
    doi:10.1056/NEJMoa2102953.

Mathematical Formulation:
    eGFR = 142 * (min(Scr / kappa, 1.0) ** alpha) * (max(Scr / kappa, 1.0) ** -1.200)
               * (0.9938 ** age) * [1.012 if female else 1.000]

Parameters:
    - Female: kappa = 0.7, alpha = -0.241, multiplier = 1.012
    - Male:   kappa = 0.9, alpha = -0.302, multiplier = 1.000
    - Scr:    Serum creatinine in mg/dL
    - Age:    Age in completed years (validated strictly for adults >= 18.0 years)

Clinical Safeguards Enforced:
    1. Zero Silent Imputation: Missing or invalid measurements return explicit unavailable status.
    2. Pediatric Exclusion: Patients aged < 18.0 years are excluded with an explicit clinical message.
    3. Physiological Range & Unit Validation: Supported units mg/dL and umol/L.
    4. Numerical Safety: Protects against zero, negative, infinite, and non-numeric inputs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("nefroai.clinical.egfr_calculator")

# Physiological operating boundaries (for warning and out-of-domain detection)
CONVENTIONAL_SCR_OPERATING_RANGE: Tuple[float, float] = (0.1, 30.0)  # mg/dL
SI_SCR_OPERATING_RANGE: Tuple[float, float] = (8.84, 2652.0)  # umol/L

# Conversion factor: 1 mg/dL = 88.42 umol/L
UMOL_TO_MGDL_FACTOR: float = 1.0 / 88.42


def decode_sex(sex: Any) -> Optional[str]:
    """Decode heterogeneous sex representations into canonical 'female' or 'male'.

    Parameters
    ----------
    sex : Any
        CDC category (1=male, 2=female), string ('male', 'female', 'M', 'F'), etc.

    Returns
    -------
    str or None
        'female', 'male', or None if unrecognized.
    """
    if pd.isna(sex):
        return None

    if isinstance(sex, (int, float, np.integer, np.floating)):
        val = int(round(sex))
        if val == 2:
            return "female"
        if val == 1:
            return "male"
        return None

    s = str(sex).strip().lower()
    if s in ["2", "2.0", "f", "female", "woman"]:
        return "female"
    if s in ["1", "1.0", "m", "male", "man"]:
        return "male"

    return None


def calculate_egfr_ckd_epi_2021(
    serum_creatinine: Any,
    age: Any,
    sex: Any,
    unit: str = "mg/dL",
) -> Dict[str, Any]:
    """Calculate estimated Glomerular Filtration Rate using race-free 2021 CKD-EPI creatinine equation.

    Parameters
    ----------
    serum_creatinine : float or convertible
        Serum creatinine measurement.
    age : float or convertible
        Patient age in years at examination (must be >= 18.0).
    sex : Any
        Patient sex (1=male, 2=female, or string).
    unit : str, default "mg/dL"
        Unit of serum creatinine ("mg/dL" or "umol/L").

    Returns
    -------
    dict
        Structured calculation results including:
        - egfr : float or None (rounded to 2 decimal places)
        - is_valid : bool
        - canonical_unit : "mL/min/1.73 m2"
        - sex_decoded : "male", "female", or None
        - scr_standardized_mg_dl : float or None
        - age_evaluated : float or None
        - equation_version : "CKD-EPI 2021 Race-Free Creatinine"
        - status : "VALID", "INVALID_INPUT", "MISSING_INPUT", or "PEDIATRIC_EXCLUDED"
        - message : Descriptive clinical explanation
        - out_of_domain : bool
    """
    # 1. Missingness checks
    if pd.isna(serum_creatinine) or pd.isna(age) or pd.isna(sex):
        missing_fields = []
        if pd.isna(serum_creatinine):
            missing_fields.append("serum_creatinine")
        if pd.isna(age):
            missing_fields.append("age")
        if pd.isna(sex):
            missing_fields.append("sex")
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": None,
            "scr_standardized_mg_dl": None,
            "age_evaluated": None,
            "is_top_coded_age": False,
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "MISSING_INPUT",
            "message": f"Cannot calculate eGFR: missing required inputs ({', '.join(missing_fields)}).",
            "out_of_domain": False,
        }

    # 2. Decode sex
    canonical_sex = decode_sex(sex)
    if canonical_sex is None:
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": None,
            "scr_standardized_mg_dl": None,
            "age_evaluated": None,
            "is_top_coded_age": False,
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": f"Cannot calculate eGFR: invalid or unrecognized sex specification ({sex!r}).",
            "out_of_domain": False,
        }

    # 3. Parse and validate age
    try:
        age_val = float(age)
    except (TypeError, ValueError):
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": None,
            "age_evaluated": None,
            "is_top_coded_age": False,
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": f"Cannot calculate eGFR: non-numeric age value ({age!r}).",
            "out_of_domain": False,
        }

    if not np.isfinite(age_val):
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": None,
            "age_evaluated": None,
            "is_top_coded_age": False,
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": "Cannot calculate eGFR: non-finite age value.",
            "out_of_domain": False,
        }

    if age_val < 18.0:
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": None,
            "age_evaluated": round(age_val, 2),
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "PEDIATRIC_EXCLUDED",
            "message": (
                f"Pediatric patient (age {age_val:.1f} years < 18.0). "
                "CKD-EPI 2021 race-free equation is clinically validated exclusively for adults aged >= 18.0 years. "
                "Pediatric evaluation requires dedicated equations (e.g. Bedside Schwartz using height and pediatric k-factors)."
            ),
            "out_of_domain": False,
        }

    if age_val > 125.0:
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": None,
            "age_evaluated": round(age_val, 2),
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": f"Cannot calculate eGFR: biologically implausible age ({age_val} years).",
            "out_of_domain": True,
        }

    # 4. Parse and standardize serum creatinine
    try:
        scr_val = float(serum_creatinine)
    except (TypeError, ValueError):
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": None,
            "age_evaluated": round(age_val, 2),
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": f"Cannot calculate eGFR: non-numeric serum creatinine value ({serum_creatinine!r}).",
            "out_of_domain": False,
        }

    if not np.isfinite(scr_val):
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": None,
            "age_evaluated": round(age_val, 2),
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": "Cannot calculate eGFR: non-finite serum creatinine value.",
            "out_of_domain": False,
        }

    if scr_val <= 0.0:
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": scr_val,
            "age_evaluated": round(age_val, 2),
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": f"Cannot calculate eGFR: non-positive serum creatinine ({scr_val}).",
            "out_of_domain": False,
        }

    # Standardize unit to mg/dL
    clean_unit = unit.strip().lower()
    if clean_unit in ["mg/dl", "mg_dl", "mgdl"]:
        scr_mgdl = scr_val
    elif clean_unit in ["umol/l", "umol_l", "umoll", "µmol/l", "micromol/l"]:
        scr_mgdl = scr_val * UMOL_TO_MGDL_FACTOR
    else:
        return {
            "egfr": None,
            "is_valid": False,
            "canonical_unit": "mL/min/1.73 m2",
            "sex_decoded": canonical_sex,
            "scr_standardized_mg_dl": None,
            "age_evaluated": round(age_val, 2),
            "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
            "status": "INVALID_INPUT",
            "message": f"Unsupported serum creatinine unit: {unit!r}. Supported units: 'mg/dL' or 'umol/L'.",
            "out_of_domain": False,
        }

    # Out-of-domain flag (calculated accurately without silent clamping)
    is_out_of_domain = (
        scr_mgdl < CONVENTIONAL_SCR_OPERATING_RANGE[0]
        or scr_mgdl > CONVENTIONAL_SCR_OPERATING_RANGE[1]
    )

    # 5. Evaluate CKD-EPI 2021 race-free equation
    is_female = (canonical_sex == "female")
    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    female_multiplier = 1.012 if is_female else 1.000

    ratio = scr_mgdl / kappa
    term1 = min(ratio, 1.0) ** alpha
    term2 = max(ratio, 1.0) ** (-1.200)
    term3 = 0.9938 ** age_val

    egfr_val = 142.0 * term1 * term2 * term3 * female_multiplier

    is_top_coded_age = bool(age_val >= 80.0)
    top_code_note = (
        " Note: Age >= 80 is top-coded at 80.0 in NHANES; true chronological age > 80 may result in slight eGFR overestimation (~0.62% per year beyond 80)."
        if is_top_coded_age else ""
    )

    return {
        "egfr": round(float(egfr_val), 2),
        "is_valid": True,
        "canonical_unit": "mL/min/1.73 m2",
        "sex_decoded": canonical_sex,
        "scr_standardized_mg_dl": round(float(scr_mgdl), 4),
        "age_evaluated": round(float(age_val), 2),
        "is_top_coded_age": is_top_coded_age,
        "equation_version": "CKD-EPI 2021 Race-Free Creatinine",
        "status": "VALID",
        "message": f"eGFR successfully calculated according to CKD-EPI 2021 race-free creatinine equation.{top_code_note}",
        "out_of_domain": is_out_of_domain,
    }


def calculate_egfr_vectorized(
    serum_creatinine: pd.Series,
    age: pd.Series,
    sex: pd.Series,
) -> pd.Series:
    """Vectorized calculation of race-free CKD-EPI 2021 eGFR over pandas Series.

    Invalid, pediatric, or missing records evaluate strictly to np.nan.

    Parameters
    ----------
    serum_creatinine : pd.Series
        Serum creatinine in mg/dL.
    age : pd.Series
        Age in years.
    sex : pd.Series
        Sex codes (1=male, 2=female).

    Returns
    -------
    pd.Series
        Calculated eGFR values in mL/min/1.73 m2 with NaN for invalid/missing cases.
    """
    scr = pd.to_numeric(serum_creatinine, errors="coerce")
    a = pd.to_numeric(age, errors="coerce")
    s = sex.apply(decode_sex)

    # Mask valid inputs: adult >= 18, scr > 0, finite, known sex
    valid_mask = (
        scr.notna()
        & a.notna()
        & s.notna()
        & np.isfinite(scr)
        & np.isfinite(a)
        & (scr > 0.0)
        & (a >= 18.0)
        & (a <= 125.0)
    )

    egfr_series = pd.Series(np.nan, index=serum_creatinine.index, dtype=float)
    if not valid_mask.any():
        return egfr_series

    # Extract valid sub-arrays
    sub_scr = scr[valid_mask].to_numpy(dtype=float)
    sub_age = a[valid_mask].to_numpy(dtype=float)
    sub_is_female = (s[valid_mask] == "female").to_numpy(dtype=bool)

    kappa = np.where(sub_is_female, 0.7, 0.9)
    alpha = np.where(sub_is_female, -0.241, -0.302)
    female_multiplier = np.where(sub_is_female, 1.012, 1.000)

    ratio = sub_scr / kappa
    term1 = np.minimum(ratio, 1.0) ** alpha
    term2 = np.maximum(ratio, 1.0) ** (-1.200)
    term3 = 0.9938 ** sub_age

    calc_vals = 142.0 * term1 * term2 * term3 * female_multiplier
    egfr_series.loc[valid_mask] = np.round(calc_vals, 2)

    return egfr_series
