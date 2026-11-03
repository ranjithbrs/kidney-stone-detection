"""NEFROAI-X Clinical Calculation Engine: KDIGO Staging & CGA Risk Grid.

Implements the Kidney Disease: Improving Global Outcomes (KDIGO) 2012 / 2024
Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease:
- GFR Categories (G1 to G5)
- Albuminuria Categories (A1 to A3)
- KDIGO CGA Classification & 4-Level Composite Risk Matrix

CRITICAL CLINICAL & METHODOLOGICAL SAFEGUARDS:
1. Zero Silent Imputation: Missing eGFR or UACR yields explicit UNAVAILABLE status.
   Never defaults missing values to G1 or A1.
2. Chronicity Limitation: A single cross-sectional laboratory measurement cannot establish
   kidney damage or reduced filtration persisting for >= 3 months. All outputs are explicitly
   designated as single-timepoint cross-sectional risk classifications, NOT confirmed chronic diagnoses.
3. Cause Designation: The etiology ('C' in CGA) is strictly flagged as UNAVAILABLE_CROSS_SECTIONAL
   unless substantiated by independent clinical history, pathology, or imaging.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("nefroai.clinical.kdigo_staging")

# =====================================================================
# Reference Definitions & Standards
# =====================================================================

GFR_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "G1": {
        "label": "G1",
        "description": "Normal or high",
        "range_ml_min": ">= 90",
        "lower_bound": 90.0,
        "upper_bound": float("inf"),
        "clinical_significance": "Normal kidney filtration function in the absence of markers of kidney damage.",
    },
    "G2": {
        "label": "G2",
        "description": "Mildly decreased",
        "range_ml_min": "60 - 89",
        "lower_bound": 60.0,
        "upper_bound": 90.0,
        "clinical_significance": "Mild reduction in filtration; may be normal for age in older adults (>65 years).",
    },
    "G3a": {
        "label": "G3a",
        "description": "Mildly to moderately decreased",
        "range_ml_min": "45 - 59",
        "lower_bound": 45.0,
        "upper_bound": 60.0,
        "clinical_significance": "Mild-to-moderate impairment; warrants nephrology evaluation and cardiovascular risk management.",
    },
    "G3b": {
        "label": "G3b",
        "description": "Moderately to severely decreased",
        "range_ml_min": "30 - 44",
        "lower_bound": 30.0,
        "upper_bound": 45.0,
        "clinical_significance": "Moderate-to-severe impairment; increased risk of progression, anemia, and metabolic bone disease.",
    },
    "G4": {
        "label": "G4",
        "description": "Severely decreased",
        "range_ml_min": "15 - 29",
        "lower_bound": 15.0,
        "upper_bound": 30.0,
        "clinical_significance": "Severe impairment; preparation for kidney replacement therapy (dialysis or transplantation).",
    },
    "G5": {
        "label": "G5",
        "description": "Kidney failure",
        "range_ml_min": "< 15",
        "lower_bound": 0.0,
        "upper_bound": 15.0,
        "clinical_significance": "Kidney failure / end-stage renal disease; requires nephrology consultation for active renal replacement.",
    },
}

ALBUMINURIA_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "A1": {
        "label": "A1",
        "description": "Normal to mildly increased",
        "range_mg_g": "< 30",
        "lower_bound": 0.0,
        "upper_bound": 30.0,
        "clinical_significance": "Physiological baseline; minimal glomerular podocyte permeability breakdown.",
    },
    "A2": {
        "label": "A2",
        "description": "Moderately increased",
        "range_mg_g": "30 - 300",
        "lower_bound": 30.0,
        "upper_bound": 300.0,
        "clinical_significance": "Microalbuminuria; early marker of diabetic/hypertensive microvascular glomerular injury.",
    },
    "A3": {
        "label": "A3",
        "description": "Severely increased",
        "range_mg_g": "> 300",
        "lower_bound": 300.0,
        "upper_bound": float("inf"),
        "clinical_significance": (
            "Severely increased albuminuria (> 300 mg/g; includes non-nephrotic and nephrotic ranges); "
            "substantial podocyte damage; high cardiovascular & progression risk. "
            "Note: true nephrotic-range proteinuria requires UACR > 2,200 mg/g (or protein > 3.5 g/24 hr)."
        ),
    },
}

KDIGO_RISK_MATRIX: Dict[Tuple[str, str], Dict[str, str]] = {
    ("G1", "A1"): {"risk_level": "Low Risk", "color": "green", "tier": 1},
    ("G1", "A2"): {"risk_level": "Moderately Increased Risk", "color": "yellow", "tier": 2},
    ("G1", "A3"): {"risk_level": "High Risk", "color": "orange", "tier": 3},
    ("G2", "A1"): {"risk_level": "Low Risk", "color": "green", "tier": 1},
    ("G2", "A2"): {"risk_level": "Moderately Increased Risk", "color": "yellow", "tier": 2},
    ("G2", "A3"): {"risk_level": "High Risk", "color": "orange", "tier": 3},
    ("G3a", "A1"): {"risk_level": "Moderately Increased Risk", "color": "yellow", "tier": 2},
    ("G3a", "A2"): {"risk_level": "High Risk", "color": "orange", "tier": 3},
    ("G3a", "A3"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G3b", "A1"): {"risk_level": "High Risk", "color": "orange", "tier": 3},
    ("G3b", "A2"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G3b", "A3"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G4", "A1"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G4", "A2"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G4", "A3"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G5", "A1"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G5", "A2"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
    ("G5", "A3"): {"risk_level": "Very High Risk", "color": "red", "tier": 4},
}

CHRONICITY_DISCLAIMER: str = (
    "CLINICAL CHRONICITY DISCLAIMER: KDIGO clinical guidelines require sustained abnormalities "
    "of kidney structure or function for >= 3 months to confirm Chronic Kidney Disease. "
    "This assessment represents a cross-sectional single-timepoint laboratory phenotype. "
    "It cannot distinguish Acute Kidney Injury (AKI), transient functional proteinuria, or dehydration "
    "from progressive CKD. Clinical adjudication by a board-certified nephrologist is mandatory."
)


# =====================================================================
# GFR Classification
# =====================================================================

def classify_gfr_category(egfr: Any) -> Dict[str, Any]:
    """Classify estimated GFR into official KDIGO GFR categories (G1 to G5).

    Strict KDIGO Criteria:
    - G1:  eGFR >= 90.0 mL/min/1.73 m2
    - G2:  60.0 <= eGFR < 90.0 mL/min/1.73 m2
    - G3a: 45.0 <= eGFR < 60.0 mL/min/1.73 m2
    - G3b: 30.0 <= eGFR < 45.0 mL/min/1.73 m2
    - G4:  15.0 <= eGFR < 30.0 mL/min/1.73 m2
    - G5:  eGFR < 15.0 mL/min/1.73 m2

    Parameters
    ----------
    egfr : float or convertible
        Calculated eGFR in mL/min/1.73 m2.

    Returns
    -------
    dict
        Structured categorization:
        - category : str or None ('G1', 'G2', 'G3a', 'G3b', 'G4', 'G5', or None)
        - description : str or None
        - range_ml_min : str or None
        - status : 'VALID', 'MISSING_INPUT', or 'INVALID_INPUT'
        - message : Clinical guidance string
    """
    if pd.isna(egfr):
        return {
            "category": None,
            "description": None,
            "range_ml_min": None,
            "status": "MISSING_INPUT",
            "message": "GFR category unavailable: missing eGFR measurement.",
        }

    try:
        val = float(egfr)
    except (TypeError, ValueError):
        return {
            "category": None,
            "description": None,
            "range_ml_min": None,
            "status": "INVALID_INPUT",
            "message": f"GFR category unavailable: non-numeric eGFR value ({egfr!r}).",
        }

    if not np.isfinite(val) or val < 0.0:
        return {
            "category": None,
            "description": None,
            "range_ml_min": None,
            "status": "INVALID_INPUT",
            "message": f"GFR category unavailable: non-finite or negative eGFR ({val}).",
        }

    if val >= 90.0:
        cat_key = "G1"
    elif val >= 60.0:
        cat_key = "G2"
    elif val >= 45.0:
        cat_key = "G3a"
    elif val >= 30.0:
        cat_key = "G3b"
    elif val >= 15.0:
        cat_key = "G4"
    else:
        cat_key = "G5"

    meta = GFR_CATEGORIES[cat_key]
    return {
        "category": cat_key,
        "description": meta["description"],
        "range_ml_min": meta["range_ml_min"],
        "clinical_significance": meta["clinical_significance"],
        "status": "VALID",
        "message": f"eGFR {val:.2f} mL/min/1.73 m2 classified as KDIGO category {cat_key} ({meta['description']}).",
    }


# =====================================================================
# Albuminuria Classification
# =====================================================================

def classify_albuminuria_category(
    uacr: Any,
    unit: str = "mg/g",
) -> Dict[str, Any]:
    """Classify Urine Albumin-to-Creatinine Ratio (UACR) into KDIGO categories (A1 to A3).

    Strict KDIGO Criteria:
    - A1: UACR < 30.0 mg/g (normal to mildly increased)
    - A2: 30.0 <= UACR <= 300.0 mg/g (moderately increased)
    - A3: UACR > 300.0 mg/g (severely increased)

    Boundary Specifications:
    - 29.99 mg/g -> A1
    - 30.00 mg/g -> A2
    - 300.00 mg/g -> A2
    - 300.01 mg/g -> A3

    Parameters
    ----------
    uacr : float or convertible
        Urine albumin-to-creatinine ratio.
    unit : str, default 'mg/g'
        Unit of measurement ('mg/g' or 'mg/mmol').

    Returns
    -------
    dict
        Structured categorization:
        - category : str or None ('A1', 'A2', 'A3', or None)
        - description : str or None
        - range_mg_g : str or None
        - status : 'VALID', 'MISSING_INPUT', or 'INVALID_INPUT'
        - message : Clinical guidance string
    """
    if pd.isna(uacr):
        return {
            "category": None,
            "description": None,
            "range_mg_g": None,
            "status": "MISSING_INPUT",
            "message": "Albuminuria category unavailable: missing UACR measurement.",
        }

    try:
        val = float(uacr)
    except (TypeError, ValueError):
        return {
            "category": None,
            "description": None,
            "range_mg_g": None,
            "status": "INVALID_INPUT",
            "message": f"Albuminuria category unavailable: non-numeric UACR value ({uacr!r}).",
        }

    if not np.isfinite(val) or val < 0.0:
        return {
            "category": None,
            "description": None,
            "range_mg_g": None,
            "status": "INVALID_INPUT",
            "message": f"Albuminuria category unavailable: non-finite or negative UACR ({val}).",
        }

    clean_unit = unit.strip().lower()
    if clean_unit in ["mg/g", "mg_g", "mgg"]:
        uacr_mgg = val
    elif clean_unit in ["mg/mmol", "mg_mmol"]:
        # 1 mg/mmol ~= 8.84 mg/g
        uacr_mgg = val * 8.84
    else:
        return {
            "category": None,
            "description": None,
            "range_mg_g": None,
            "status": "INVALID_INPUT",
            "message": f"Albuminuria category unavailable: unsupported unit ({unit!r}).",
        }

    if uacr_mgg < 30.0:
        cat_key = "A1"
    elif uacr_mgg <= 300.0:
        cat_key = "A2"
    else:
        cat_key = "A3"

    meta = ALBUMINURIA_CATEGORIES[cat_key]
    return {
        "category": cat_key,
        "description": meta["description"],
        "range_mg_g": meta["range_mg_g"],
        "clinical_significance": meta["clinical_significance"],
        "status": "VALID",
        "message": f"UACR {uacr_mgg:.2f} mg/g classified as KDIGO category {cat_key} ({meta['description']}).",
    }


# =====================================================================
# KDIGO CGA Assembly & Composite Risk Grid
# =====================================================================

def classify_kdigo_composite_risk(
    gfr_category: Optional[str],
    albuminuria_category: Optional[str],
    cause: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble KDIGO CGA classification and map to composite risk level.

    CGA Architecture:
    - Cause (C): Primary underlying etiology (e.g. Diabetic Kidney Disease, Hypertensive Nephrosclerosis).
      In cross-sectional datasets like NHANES, cause is explicitly 'UNAVAILABLE_CROSS_SECTIONAL'.
    - GFR Category (G): G1, G2, G3a, G3b, G4, G5.
    - Albuminuria Category (A): A1, A2, A3.

    Composite Risk Grid Levels:
    - Low Risk (Green)
    - Moderately Increased Risk (Yellow)
    - High Risk (Orange)
    - Very High Risk (Red)

    Parameters
    ----------
    gfr_category : str or None
        KDIGO GFR category ('G1' to 'G5').
    albuminuria_category : str or None
        KDIGO Albuminuria category ('A1' to 'A3').
    cause : str, optional
        Documented clinical cause. Defaults to 'UNAVAILABLE_CROSS_SECTIONAL'.

    Returns
    -------
    dict
        Structured CGA assessment including composite risk level, color, and chronicity safeguards.
    """
    cause_str = cause if cause else "UNAVAILABLE_CROSS_SECTIONAL"
    cga_string = f"C: {cause_str} | G: {gfr_category or 'Unavailable'} | A: {albuminuria_category or 'Unavailable'}"

    # Verify both G and A are valid
    if not gfr_category or not albuminuria_category:
        missing = []
        if not gfr_category:
            missing.append("GFR category (G)")
        if not albuminuria_category:
            missing.append("Albuminuria category (A)")
        return {
            "cga_classification": cga_string,
            "cause": cause_str,
            "gfr_category": gfr_category,
            "albuminuria_category": albuminuria_category,
            "composite_risk_level": None,
            "risk_color": "gray",
            "risk_tier": None,
            "clinical_interpretation": None,
            "is_complete": False,
            "chronicity_confirmed": False,
            "status": "INCOMPLETE",
            "message": f"Cannot determine KDIGO composite risk: missing {', '.join(missing)}.",
            "chronicity_disclaimer": CHRONICITY_DISCLAIMER,
        }

    g_clean = str(gfr_category).strip()
    a_clean = str(albuminuria_category).strip()
    pair = (g_clean, a_clean)

    if pair not in KDIGO_RISK_MATRIX:
        return {
            "cga_classification": cga_string,
            "cause": cause_str,
            "gfr_category": gfr_category,
            "albuminuria_category": albuminuria_category,
            "composite_risk_level": None,
            "risk_color": "gray",
            "risk_tier": None,
            "clinical_interpretation": None,
            "is_complete": False,
            "chronicity_confirmed": False,
            "status": "INVALID_CATEGORY_PAIR",
            "message": f"Unrecognized category combination: {pair}.",
            "chronicity_disclaimer": CHRONICITY_DISCLAIMER,
        }

    risk_info = KDIGO_RISK_MATRIX[pair]

    # Clinical interpretation emphasizing KDIGO guidelines:
    # G1/A1 and G2/A1 represent Low Risk and do NOT constitute CKD in the absence of independent markers of damage.
    if pair in [("G1", "A1"), ("G2", "A1")]:
        clinical_interpretation = (
            "Low Risk; does NOT constitute Chronic Kidney Disease (CKD) in the absence of independent "
            "markers of kidney damage (e.g., persistent hematuria, structural imaging abnormalities, "
            "or biopsy-proven histological damage) sustained for >= 3 months."
        )
    else:
        clinical_interpretation = (
            f"{risk_info['risk_level']} (Tier {risk_info['tier']}); increased risk of CKD progression "
            "and cardiovascular events. Requires clinical correlation and repeat confirmation at >= 3 months to confirm chronicity."
        )

    return {
        "cga_classification": cga_string,
        "cause": cause_str,
        "gfr_category": g_clean,
        "albuminuria_category": a_clean,
        "composite_risk_level": risk_info["risk_level"],
        "risk_color": risk_info["color"],
        "risk_tier": risk_info["tier"],
        "clinical_interpretation": clinical_interpretation,
        "is_complete": True,
        "chronicity_confirmed": False,
        "status": "VALID",
        "message": (
            f"Cross-sectional KDIGO CGA staging: {g_clean}{a_clean} corresponds to "
            f"{risk_info['risk_level']} (Tier {risk_info['tier']})."
        ),
        "chronicity_disclaimer": CHRONICITY_DISCLAIMER,
    }
