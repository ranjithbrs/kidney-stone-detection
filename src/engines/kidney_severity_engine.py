"""NEFROAI-X Engine 2: Clinical CKD Severity Assessment & KDIGO CGA Staging Engine.

Provides automated, mathematically rigorous, and clinically safeguarded
evaluation of chronic kidney disease severity based on laboratory and examination data.

Architectural Scope:
- Calculates race-free 2021 CKD-EPI estimated Glomerular Filtration Rate (eGFR).
- Classifies KDIGO GFR Categories (G1 to G5).
- Classifies KDIGO Albuminuria Categories (A1 to A3).
- Assembles KDIGO CGA Classification and evaluates 4-tier Composite Risk Matrix.
- Enforces strict clinical safeguards: Zero silent imputation, pediatric exclusion,
  cross-sectional chronicity boundaries, and denominator preservation.

Engine Independence:
- Engine 2 operates strictly independently of Engine 1 (UCI screening model).
- Does not merge UCI classification labels with NHANES population cohorts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.clinical.egfr_calculator import (
    calculate_egfr_ckd_epi_2021,
    calculate_egfr_vectorized,
    decode_sex,
)
from src.clinical.kdigo_staging import (
    CHRONICITY_DISCLAIMER,
    classify_albuminuria_category,
    classify_gfr_category,
    classify_kdigo_composite_risk,
)

logger = logging.getLogger("nefroai.engines.kidney_severity_engine")


class KidneySeverityEngine:
    """Clinical Decision Support Engine for CKD Severity Assessment & KDIGO CGA Staging."""

    def __init__(self, name: str = "NEFROAI-X Engine 2 (KDIGO Severity)") -> None:
        self.name = name
        self.version = "2.0.0-phase5.step2"
        self.chronicity_disclaimer = CHRONICITY_DISCLAIMER

    def assess_patient(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Assess kidney disease severity and KDIGO risk for a single patient record.

        Parameters
        ----------
        record : dict
            Dictionary containing patient measurements. Expected keys:
            - 'serum_creatinine' (or 'LBXSCR', 'sc'): float, mg/dL
            - 'uacr' (or 'URDACT'): float, mg/g
            - 'age' (or 'age_years', 'RIDAGEYR'): float, years
            - 'sex' (or 'sex_code', 'RIAGENDR'): int or str (1=male, 2=female)
            - Optional: 'age_months_exam' (or 'RIDEXAGM'), 'urine_albumin_comment_code',
              'urine_creatinine_comment_code', 'cause'

        Returns
        -------
        dict
            Comprehensive structured severity assessment.
        """
        # Resolve serum creatinine
        scr = (
            record.get("serum_creatinine")
            if "serum_creatinine" in record
            else (record.get("LBXSCR") if "LBXSCR" in record else record.get("sc"))
        )

        # Resolve UACR
        uacr = (
            record.get("uacr")
            if "uacr" in record
            else (record.get("URDACT") if "URDACT" in record else record.get("uacr_mg_g"))
        )

        # Resolve age: prefer examination age if months given, else screening age
        exam_m = record.get("age_months_exam", record.get("RIDEXAGM"))
        screening_age = record.get("age_years", record.get("RIDAGEYR", record.get("age")))

        if exam_m is not None and pd.notna(exam_m) and float(exam_m) >= 216.0:
            eval_age = float(exam_m) / 12.0
            age_source = "examination_age_exact"
        else:
            eval_age = float(screening_age) if pd.notna(screening_age) else None
            age_source = "screening_age"

        # Resolve sex
        sex = record.get("sex_code", record.get("RIAGENDR", record.get("sex")))

        # Check QC comment codes if present
        qc_alb = record.get("urine_albumin_comment_code", record.get("URDUMALC"))
        qc_cr = record.get("urine_creatinine_comment_code", record.get("URDUCRLC"))
        has_detection_limit_impact = bool(
            (pd.notna(qc_alb) and float(qc_alb) == 1.0)
            or (pd.notna(qc_cr) and float(qc_cr) == 1.0)
        )

        # 1. Calculate eGFR
        egfr_result = calculate_egfr_ckd_epi_2021(
            serum_creatinine=scr,
            age=eval_age,
            sex=sex,
            unit="mg/dL",
        )

        # 2. Classify GFR Category
        gfr_cat_result = classify_gfr_category(egfr_result["egfr"])

        # 3. Classify Albuminuria Category
        alb_cat_result = classify_albuminuria_category(uacr, unit="mg/g")

        # 4. Assemble KDIGO CGA Classification and Composite Risk
        cause = record.get("cause", "UNAVAILABLE_CROSS_SECTIONAL")
        cga_result = classify_kdigo_composite_risk(
            gfr_category=gfr_cat_result["category"],
            albuminuria_category=alb_cat_result["category"],
            cause=cause,
        )

        # Check eligibility and completeness
        is_adult = (eval_age is not None and eval_age >= 18.0)
        is_complete = bool(egfr_result["is_valid"] and alb_cat_result["status"] == "VALID")

        return {
            "engine": self.name,
            "version": self.version,
            "patient_id": record.get("participant_id", record.get("SEQN", "ANONYMOUS")),
            "is_adult": is_adult,
            "age_evaluated_years": eval_age,
            "age_source": age_source,
            "sex_decoded": egfr_result["sex_decoded"],
            "filtration_assessment": {
                "egfr": egfr_result["egfr"],
                "unit": egfr_result["canonical_unit"],
                "equation": egfr_result["equation_version"],
                "gfr_category": gfr_cat_result["category"],
                "gfr_description": gfr_cat_result["description"],
                "gfr_range_ml_min": gfr_cat_result["range_ml_min"],
                "is_valid": egfr_result["is_valid"],
                "status": egfr_result["status"],
                "message": egfr_result["message"],
            },
            "albuminuria_assessment": {
                "uacr": float(uacr) if pd.notna(uacr) else None,
                "unit": "mg/g",
                "albuminuria_category": alb_cat_result["category"],
                "albuminuria_description": alb_cat_result["description"],
                "albuminuria_range_mg_g": alb_cat_result["range_mg_g"],
                "is_valid": alb_cat_result["status"] == "VALID",
                "status": alb_cat_result["status"],
                "message": alb_cat_result["message"],
                "detection_limit_flag": has_detection_limit_impact,
            },
            "kdigo_cga_staging": {
                "cga_string": cga_result["cga_classification"],
                "cause": cga_result["cause"],
                "gfr_category": cga_result["gfr_category"],
                "albuminuria_category": cga_result["albuminuria_category"],
                "composite_risk_level": cga_result["composite_risk_level"],
                "risk_color": cga_result["risk_color"],
                "risk_tier": cga_result["risk_tier"],
                "is_complete": cga_result["is_complete"],
                "clinical_interpretation": cga_result.get("clinical_interpretation"),
                "status": cga_result["status"],
                "message": cga_result["message"],
            },
            "clinical_governance": {
                "chronicity_confirmed": False,
                "assessment_nature": "Cross-Sectional Single-Timepoint Screening Phenotype",
                "is_complete_severity_record": is_complete,
                "disclaimer": self.chronicity_disclaimer,
            },
        }

    def assess_cohort(
        self,
        df: pd.DataFrame,
        use_examination_age: bool = True,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Perform cohort-level CKD severity assessment and compute KDIGO grid metrics.

        Parameters
        ----------
        df : pd.DataFrame
            Merged NHANES dataset or standardized feature dataset.
        use_examination_age : bool, default True
            Whether to use exact age in months at examination for participants aged 0-19.

        Returns
        -------
        tuple of (pd.DataFrame, dict)
            Augmented DataFrame with staging columns, and structured cohort severity audit.
        """
        augmented = df.copy()
        total_participants = len(df)

        # Resolve column names
        age_col = "RIDAGEYR" if "RIDAGEYR" in df.columns else ("age_years" if "age_years" in df.columns else None)
        exam_age_col = "RIDEXAGM" if "RIDEXAGM" in df.columns else ("age_months_exam" if "age_months_exam" in df.columns else None)
        sex_col = "RIAGENDR" if "RIAGENDR" in df.columns else ("sex_code" if "sex_code" in df.columns else None)
        scr_col = "LBXSCR" if "LBXSCR" in df.columns else ("serum_creatinine" if "serum_creatinine" in df.columns else None)
        uacr_col = "URDACT" if "URDACT" in df.columns else ("uacr" if "uacr" in df.columns else None)
        statr_col = "RIDSTATR" if "RIDSTATR" in df.columns else ("interview_exam_status" if "interview_exam_status" in df.columns else None)

        if not all([age_col, sex_col, scr_col, uacr_col]):
            raise ValueError(
                f"Missing required columns for severity staging. "
                f"Resolved: age={age_col}, sex={sex_col}, scr={scr_col}, uacr={uacr_col}"
            )

        # Determine adult eligibility using exact examination age protocol
        screening_age = augmented[age_col].astype(float)
        is_adult_screening = screening_age >= 18.0

        if use_examination_age and exam_age_col and exam_age_col in augmented.columns:
            exam_m = augmented[exam_age_col].apply(
                lambda v: 0.0 if (pd.notna(v) and abs(float(v)) < 1e-10) else (float(v) if pd.notna(v) else np.nan)
            )
            is_adult_arr = np.where(exam_m.notna(), exam_m >= 216.0, is_adult_screening)
            is_adult = pd.Series(is_adult_arr, index=augmented.index, dtype=bool)
            # Calculated age: exact exam age in years if exam_m >= 216, else screening age
            calc_age = np.where(exam_m.notna() & (exam_m >= 216.0), exam_m / 12.0, screening_age)
        else:
            is_adult = is_adult_screening
            calc_age = screening_age

        is_pediatric = ~is_adult
        augmented["is_adult"] = is_adult
        augmented["evaluation_age_years"] = calc_age

        # Check interview vs MEC status
        if statr_col and statr_col in augmented.columns:
            is_mec = (augmented[statr_col] == 2.0)
            is_int_only = (augmented[statr_col] == 1.0)
        else:
            is_mec = pd.Series(True, index=augmented.index)
            is_int_only = pd.Series(False, index=augmented.index)

        augmented["is_mec_examined"] = is_mec
        augmented["is_interview_only"] = is_int_only

        # Calculate eGFR vectorized
        egfr_series = calculate_egfr_vectorized(
            serum_creatinine=augmented[scr_col],
            age=pd.Series(calc_age, index=augmented.index),
            sex=augmented[sex_col],
        )
        augmented["egfr_2021"] = egfr_series

        # Categorize GFR
        def _get_gfr_cat(val: Any) -> Optional[str]:
            res = classify_gfr_category(val)
            return res["category"]

        augmented["gfr_category"] = egfr_series.apply(_get_gfr_cat)

        # Categorize Albuminuria
        def _get_alb_cat(val: Any) -> Optional[str]:
            res = classify_albuminuria_category(val)
            return res["category"]

        augmented["albuminuria_category"] = augmented[uacr_col].apply(_get_alb_cat)

        # KDIGO Composite Risk
        def _get_kdigo_risk(row: pd.Series) -> Tuple[Optional[str], str, Optional[int]]:
            g = row["gfr_category"]
            a = row["albuminuria_category"]
            res = classify_kdigo_composite_risk(g, a)
            return res["composite_risk_level"], res["risk_color"], res["risk_tier"]

        risk_tuples = augmented.apply(_get_kdigo_risk, axis=1)
        augmented["kdigo_risk_level"] = [t[0] for t in risk_tuples]
        augmented["kdigo_risk_color"] = [t[1] for t in risk_tuples]
        augmented["kdigo_risk_tier"] = [t[2] for t in risk_tuples]

        # Complete case mask: adult + MEC examined + non-null eGFR + non-null albuminuria category
        is_complete_severity = (
            is_adult
            & augmented["egfr_2021"].notna()
            & augmented["albuminuria_category"].notna()
            & augmented["kdigo_risk_level"].notna()
        )
        augmented["is_complete_severity_record"] = is_complete_severity

        # Complete adult cohort subset
        complete_adult_df = augmented[is_complete_severity]
        n_complete_adults = len(complete_adult_df)

        # Compute empirical G-category distribution
        gfr_distribution = (
            complete_adult_df["gfr_category"].value_counts().to_dict()
            if n_complete_adults > 0 else {}
        )
        # Ensure all G categories present in distribution dictionary
        gfr_counts_ordered = {k: int(gfr_distribution.get(k, 0)) for k in ["G1", "G2", "G3a", "G3b", "G4", "G5"]}

        # Compute empirical A-category distribution
        alb_distribution = (
            complete_adult_df["albuminuria_category"].value_counts().to_dict()
            if n_complete_adults > 0 else {}
        )
        alb_counts_ordered = {k: int(alb_distribution.get(k, 0)) for k in ["A1", "A2", "A3"]}

        # Compute empirical KDIGO Composite Risk distribution
        risk_distribution = (
            complete_adult_df["kdigo_risk_level"].value_counts().to_dict()
            if n_complete_adults > 0 else {}
        )
        risk_counts_ordered = {
            k: int(risk_distribution.get(k, 0))
            for k in ["Low Risk", "Moderately Increased Risk", "High Risk", "Very High Risk"]
        }

        # 6x3 Crosstab Matrix
        crosstab_dict: Dict[str, Dict[str, int]] = {}
        for g_k in ["G1", "G2", "G3a", "G3b", "G4", "G5"]:
            crosstab_dict[g_k] = {}
            for a_k in ["A1", "A2", "A3"]:
                cell_count = int(
                    ((complete_adult_df["gfr_category"] == g_k) & (complete_adult_df["albuminuria_category"] == a_k)).sum()
                )
                crosstab_dict[g_k][a_k] = cell_count

        # Denominator counts
        n_adults_total = int(is_adult.sum())
        n_adults_mec = int((is_adult & is_mec).sum())
        n_adults_int_only = int((is_adult & is_int_only).sum())
        n_pediatric_total = int(is_pediatric.sum())
        n_pediatric_mec = int((is_pediatric & is_mec).sum())
        n_pediatric_int_only = int((is_pediatric & is_int_only).sum())

        audit_summary: Dict[str, Any] = {
            "engine": self.name,
            "version": self.version,
            "total_records_processed": total_participants,
            "cohort_denominators": {
                "adult_population_denominator": n_adults_total,
                "mec_examined_adult_denominator": n_adults_mec,
                "interview_only_adult_denominator": n_adults_int_only,
                "pediatric_population_denominator": n_pediatric_total,
                "mec_examined_pediatric_denominator": n_pediatric_mec,
                "interview_only_pediatric_denominator": n_pediatric_int_only,
            },
            "complete_adult_severity_cohort": {
                "complete_records_count": n_complete_adults,
                "retention_of_all_sampled_adults_pct": round((n_complete_adults / max(n_adults_total, 1)) * 100.0, 2),
                "retention_of_mec_examined_adults_pct": round((n_complete_adults / max(n_adults_mec, 1)) * 100.0, 2),
                "share_of_total_population_sample_pct": round((n_complete_adults / max(total_participants, 1)) * 100.0, 2),
            },
            "gfr_category_distribution": {
                "counts": gfr_counts_ordered,
                "percentages": {
                    k: round((v / max(n_complete_adults, 1)) * 100.0, 2)
                    for k, v in gfr_counts_ordered.items()
                },
            },
            "albuminuria_category_distribution": {
                "counts": alb_counts_ordered,
                "percentages": {
                    k: round((v / max(n_complete_adults, 1)) * 100.0, 2)
                    for k, v in alb_counts_ordered.items()
                },
            },
            "kdigo_composite_risk_distribution": {
                "counts": risk_counts_ordered,
                "percentages": {
                    k: round((v / max(n_complete_adults, 1)) * 100.0, 2)
                    for k, v in risk_counts_ordered.items()
                },
            },
            "kdigo_grid_cross_tabulation": crosstab_dict,
            "clinical_governance": {
                "chronicity_confirmed": False,
                "assessment_nature": "Cross-Sectional Single-Timepoint Screening Phenotype",
                "disclaimer": self.chronicity_disclaimer,
            },
        }

        return augmented, audit_summary
