"""NEFROAI-X Tangri 4-Variable Kidney Failure Risk Equation (KFRE) Calculator.

Implements the published, multinational validated 4-variable KFRE (Tangri et al., JAMA 2016)
to predict the 2-year and 5-year risk of progression to kidney failure (dialysis or kidney
transplant) in patients with chronic kidney disease (CKD Stages G3–G5).

Clinical & Mathematical References:
1. Tangri N, et al. A Predictive Model for Progression of Chronic Kidney Disease to Kidney Failure.
   JAMA. 2011;305(15):1553-1559. doi:10.1001/jama.2011.451.
2. Tangri N, et al. Multinational Assessment of Accuracy of Equations for Predicting Risk of Kidney
   Failure: A Meta-analysis. JAMA. 2016;315(2):164–174. doi:10.1001/jama.2015.18202.
3. KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("nefroai.kfre_calculator")


class KFRECalibrationProfile(str, Enum):
    """Supported calibration profiles for the 4-variable KFRE."""

    ORIGINAL_TANGRI = "original_tangri"
    NORTH_AMERICA = "north_america"
    NON_NORTH_AMERICA = "non_north_america"


# Published baseline survival probabilities (S0) from Tangri et al., JAMA 2016 (eAppendix 2)
KFRE_BASELINE_SURVIVAL: Dict[str, Dict[str, float]] = {
    KFRECalibrationProfile.ORIGINAL_TANGRI.value: {
        "s0_2year": 0.9750,
        "s0_5year": 0.9240,
        "description": "Original development cohort baseline survival (Tangri et al. 2011/2016).",
    },
    KFRECalibrationProfile.NORTH_AMERICA.value: {
        "s0_2year": 0.9751,
        "s0_5year": 0.8996,
        "description": "Recalibrated baseline survival for North American cohorts (Tangri et al. JAMA 2016).",
    },
    KFRECalibrationProfile.NON_NORTH_AMERICA.value: {
        "s0_2year": 0.9832,
        "s0_5year": 0.9365,
        "description": "Recalibrated baseline survival for non-North American international cohorts (Tangri et al. JAMA 2016).",
    },
}

# Published Cox proportional hazards centering constants and beta coefficients (Tangri et al. 2016)
BETA_AGE = -0.2201
BETA_SEX = 0.2467
BETA_EGFR = -0.5567
BETA_ACR = 0.4510

CENTER_AGE = 7.036
CENTER_SEX = 0.5642
CENTER_EGFR = 7.222
CENTER_ACR = 5.137

KFRE_DISCLAIMER = (
    "DISCLAIMER: The Kidney Failure Risk Equation (KFRE) is an investigational clinical risk stratification "
    "tool intended solely for patients with confirmed CKD Stages G3–G5 (eGFR < 60 mL/min/1.73 m2). It estimates "
    "the statistical probability of progression to Kidney Failure / Kidney Replacement Therapy (dialysis or kidney "
    "transplantation) over 2-year and 5-year horizons. It does not independently establish a chronic diagnosis and "
    "does not replace board-certified nephrologist clinical judgment. Note that the non-North American recalibration "
    "represents a broad international cohort calibration and has not been validated as an India-specific clinical prediction model."
)


@dataclass(frozen=True)
class KFREInput:
    """Input parameters for the 4-variable Kidney Failure Risk Equation.

    Attributes
    ----------
    age : float
        Age in completed years (must be adult: >= 18).
    sex : Union[int, str, float]
        Biological sex: male = 1, female = 0, or string ('male', 'female', 'm', 'f').
    egfr : float
        Estimated Glomerular Filtration Rate in mL/min/1.73 m2.
    uacr : float
        Urine Albumin-to-Creatinine Ratio (ACR) in mg/g.
    calibration_profile : str, default='north_america'
        Calibration profile: 'original_tangri', 'north_america', or 'non_north_america'.
    """

    age: float
    sex: Union[int, str, float]
    egfr: float
    uacr: float
    calibration_profile: str = KFRECalibrationProfile.NORTH_AMERICA.value


@dataclass(frozen=True)
class KFREResult:
    """Comprehensive result of the 4-variable KFRE calculation."""

    is_valid: bool
    is_applicable: bool
    risk_2year: Optional[float]
    risk_5year: Optional[float]
    risk_2year_percent: Optional[float]
    risk_5year_percent: Optional[float]
    linear_predictor: Optional[float]
    calibration_profile: str
    s0_2year: Optional[float]
    s0_5year: Optional[float]
    age_evaluated: Optional[float]
    sex_evaluated: Optional[str]
    male_code: Optional[float]
    egfr_evaluated: Optional[float]
    uacr_evaluated: Optional[float]
    applicability_status: str
    message: str
    disclaimer: str
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a standardized dictionary."""
        return {
            "is_valid": self.is_valid,
            "is_applicable": self.is_applicable,
            "risk_2year": self.risk_2year,
            "risk_5year": self.risk_5year,
            "risk_2year_percent": self.risk_2year_percent,
            "risk_5year_percent": self.risk_5year_percent,
            "linear_predictor": self.linear_predictor,
            "calibration_profile": self.calibration_profile,
            "s0_2year": self.s0_2year,
            "s0_5year": self.s0_5year,
            "age_evaluated": self.age_evaluated,
            "sex_evaluated": self.sex_evaluated,
            "male_code": self.male_code,
            "egfr_evaluated": self.egfr_evaluated,
            "uacr_evaluated": self.uacr_evaluated,
            "applicability_status": self.applicability_status,
            "message": self.message,
            "disclaimer": self.disclaimer,
            "validation_errors": self.validation_errors,
        }


def _decode_kfre_sex(sex_val: Any) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Decode and validate sex input for KFRE.

    Returns
    -------
    Tuple[male_code, sex_str, error_message]
        male_code is 1.0 (male), 0.0 (female), or a float in [0.0, 1.0] for exact mathematical centering.
    """
    if sex_val is None:
        return None, None, "Sex is missing. Sex must be specified (male/female or 1/0)."

    if isinstance(sex_val, (int, float)):
        if math.isnan(sex_val) or math.isinf(sex_val):
            return None, None, "Sex code cannot be NaN or infinite."
        if sex_val == 1.0 or sex_val == 1:
            return 1.0, "male", None
        if sex_val == 0.0 or sex_val == 0:
            return 0.0, "female", None
        # Allow exact mathematical centering float (e.g. 0.5642)
        if 0.0 <= sex_val <= 1.0:
            return float(sex_val), f"centered_sex_{sex_val:.4f}", None
        return None, None, f"Numeric sex code must be 1 (male), 0 (female), or in [0, 1]; got {sex_val}."

    if isinstance(sex_val, str):
        cleaned = sex_val.strip().lower()
        if cleaned in ("male", "m", "1"):
            return 1.0, "male", None
        if cleaned in ("female", "f", "0"):
            return 0.0, "female", None
        return None, None, f"Unrecognized sex string: '{sex_val}'. Expected 'male' or 'female'."

    return None, None, f"Unsupported sex type: {type(sex_val)}."


def calculate_kfre(
    age: Optional[Union[float, int, KFREInput, Dict[str, Any]]] = None,
    sex: Optional[Union[int, str, float]] = None,
    egfr: Optional[float] = None,
    uacr: Optional[float] = None,
    calibration_profile: Optional[str] = None,
) -> KFREResult:
    """Calculate the published 4-variable Kidney Failure Risk Equation (Tangri et al. 2016).

    Parameters
    ----------
    age : Union[float, int, KFREInput, Dict[str, Any]]
        Patient age in completed years, or a KFREInput dataclass/dict.
    sex : Optional[Union[int, str, float]]
        Biological sex: male = 1, female = 0, or string ('male', 'female').
    egfr : Optional[float]
        Estimated GFR in mL/min/1.73 m2.
    uacr : Optional[float]
        Urine Albumin-to-Creatinine Ratio (ACR) in mg/g.
    calibration_profile : Optional[str], default='north_america'
        One of 'original_tangri', 'north_america', 'non_north_america'.

    Returns
    -------
    KFREResult
        Structured result containing 2-year and 5-year kidney failure risk probabilities.
    """
    # 1. Unpack input if passed as KFREInput or dict
    if isinstance(age, KFREInput):
        actual_profile = calibration_profile if calibration_profile is not None else age.calibration_profile
        return calculate_kfre(
            age=age.age,
            sex=age.sex,
            egfr=age.egfr,
            uacr=age.uacr,
            calibration_profile=actual_profile,
        )
    elif isinstance(age, dict):
        actual_profile = calibration_profile if calibration_profile is not None else age.get("calibration_profile")
        return calculate_kfre(
            age=age.get("age"),
            sex=age.get("sex"),
            egfr=age.get("egfr"),
            uacr=age.get("uacr", age.get("acr")),
            calibration_profile=actual_profile,
        )

    # Resolve calibration profile key
    profile_key = str(calibration_profile or KFRECalibrationProfile.NORTH_AMERICA.value).strip().lower()
    if profile_key not in KFRE_BASELINE_SURVIVAL:
        valid_keys = list(KFRE_BASELINE_SURVIVAL.keys())
        return KFREResult(
            is_valid=False,
            is_applicable=False,
            risk_2year=None,
            risk_5year=None,
            risk_2year_percent=None,
            risk_5year_percent=None,
            linear_predictor=None,
            calibration_profile=profile_key,
            s0_2year=None,
            s0_5year=None,
            age_evaluated=None,
            sex_evaluated=None,
            male_code=None,
            egfr_evaluated=None,
            uacr_evaluated=None,
            applicability_status="INVALID_CALIBRATION_PROFILE",
            message=f"Unknown calibration profile: '{profile_key}'. Valid profiles are: {valid_keys}.",
            disclaimer=KFRE_DISCLAIMER,
            validation_errors=[f"Unsupported calibration profile: '{profile_key}'."],
        )

    s0_table = KFRE_BASELINE_SURVIVAL[profile_key]
    s0_2yr = s0_table["s0_2year"]
    s0_5yr = s0_table["s0_5year"]

    errors: List[str] = []

    # 2. Defensive Validation: Age
    eval_age: Optional[float] = None
    if age is None:
        errors.append("Age is missing. Age is required for KFRE evaluation.")
    else:
        try:
            f_age = float(age)
            if math.isnan(f_age) or math.isinf(f_age):
                errors.append("Age cannot be NaN or infinite.")
            elif f_age < 18.0:
                errors.append(f"Age {f_age:.1f} is invalid. KFRE is validated exclusively for adult patients (age >= 18).")
            elif f_age > 120.0:
                errors.append(f"Age {f_age:.1f} exceeds plausible human biological domain (max 120).")
            else:
                eval_age = f_age
        except (ValueError, TypeError):
            errors.append(f"Age value '{age}' could not be parsed as a valid numeric float.")

    # 3. Defensive Validation: Sex
    male_code, sex_str, sex_err = _decode_kfre_sex(sex)
    if sex_err:
        errors.append(sex_err)

    # 4. Defensive Validation: eGFR
    eval_egfr: Optional[float] = None
    if egfr is None:
        errors.append("eGFR is missing. Filtration rate is required for KFRE evaluation.")
    else:
        try:
            f_egfr = float(egfr)
            if math.isnan(f_egfr) or math.isinf(f_egfr):
                errors.append("eGFR cannot be NaN or infinite.")
            elif f_egfr <= 0.0:
                errors.append(f"eGFR {f_egfr:.2f} is invalid. eGFR must be strictly greater than 0 mL/min/1.73 m2.")
            else:
                eval_egfr = f_egfr
        except (ValueError, TypeError):
            errors.append(f"eGFR value '{egfr}' could not be parsed as a valid numeric float.")

    # 5. Defensive Validation: UACR
    eval_uacr: Optional[float] = None
    if uacr is None:
        errors.append("UACR is missing. Albuminuria measurement is required for KFRE evaluation.")
    else:
        try:
            f_uacr = float(uacr)
            if math.isnan(f_uacr) or math.isinf(f_uacr):
                errors.append("UACR cannot be NaN or infinite.")
            elif f_uacr <= 0.0:
                errors.append(
                    f"UACR {f_uacr:.2f} is invalid. UACR must be strictly greater than 0 mg/g for logarithmic transformation."
                )
            else:
                eval_uacr = f_uacr
        except (ValueError, TypeError):
            errors.append(f"UACR value '{uacr}' could not be parsed as a valid numeric float.")

    # Return validation error response if any input is invalid
    if errors or eval_age is None or male_code is None or eval_egfr is None or eval_uacr is None:
        return KFREResult(
            is_valid=False,
            is_applicable=False,
            risk_2year=None,
            risk_5year=None,
            risk_2year_percent=None,
            risk_5year_percent=None,
            linear_predictor=None,
            calibration_profile=profile_key,
            s0_2year=s0_2yr,
            s0_5year=s0_5yr,
            age_evaluated=eval_age,
            sex_evaluated=sex_str,
            male_code=male_code,
            egfr_evaluated=eval_egfr,
            uacr_evaluated=eval_uacr,
            applicability_status="INVALID_INPUTS",
            message=f"KFRE input validation failed with {len(errors)} error(s): {'; '.join(errors)}",
            disclaimer=KFRE_DISCLAIMER,
            validation_errors=errors,
        )

    # 6. Clinical Applicability Scope Gate (CKD Stages G3–G5: eGFR < 60)
    # The KFRE is validated exclusively for patients with established CKD Stages G3–G5.
    if eval_egfr >= 60.0:
        return KFREResult(
            is_valid=True,
            is_applicable=False,
            risk_2year=None,
            risk_5year=None,
            risk_2year_percent=None,
            risk_5year_percent=None,
            linear_predictor=None,
            calibration_profile=profile_key,
            s0_2year=s0_2yr,
            s0_5year=s0_5yr,
            age_evaluated=eval_age,
            sex_evaluated=sex_str,
            male_code=male_code,
            egfr_evaluated=eval_egfr,
            uacr_evaluated=eval_uacr,
            applicability_status="OUT_OF_SCOPE_GFR_STAGE_G1_G2",
            message=(
                f"KFRE is out of scope for eGFR = {eval_egfr:.1f} mL/min/1.73 m2 (KDIGO Stages G1/G2). "
                f"The 4-variable equation is validated exclusively for CKD Stages G3–G5 (eGFR < 60 mL/min/1.73 m2). "
                f"Risk estimates are withheld to avoid clinically misleading prognostications."
            ),
            disclaimer=KFRE_DISCLAIMER,
            validation_errors=[],
        )

    # 7. Published Linear Predictor Calculation
    # LP = -0.2201 * (age/10 - 7.036) + 0.2467 * (male - 0.5642) - 0.5567 * (egfr/5 - 7.222) + 0.4510 * (ln(ACR) - 5.137)
    term_age = BETA_AGE * ((eval_age / 10.0) - CENTER_AGE)
    term_sex = BETA_SEX * (male_code - CENTER_SEX)
    term_egfr = BETA_EGFR * ((eval_egfr / 5.0) - CENTER_EGFR)
    term_acr = BETA_ACR * (math.log(eval_uacr) - CENTER_ACR)

    lp = term_age + term_sex + term_egfr + term_acr

    # Defensive bounding of linear predictor to prevent numerical overflow
    lp_bounded = max(-20.0, min(20.0, lp))
    exp_lp = math.exp(lp_bounded)

    # 8. Cumulative Risk Calculation: Risk = 1 - S0^exp(LP)
    # Risk is mathematically bounded between 0.0 and 1.0
    r_2yr = 1.0 - math.pow(s0_2yr, exp_lp)
    r_5yr = 1.0 - math.pow(s0_5yr, exp_lp)

    r_2yr_bounded = max(0.0, min(1.0, r_2yr))
    r_5yr_bounded = max(0.0, min(1.0, r_5yr))

    return KFREResult(
        is_valid=True,
        is_applicable=True,
        risk_2year=round(r_2yr_bounded, 4),
        risk_5year=round(r_5yr_bounded, 4),
        risk_2year_percent=round(r_2yr_bounded * 100.0, 2),
        risk_5year_percent=round(r_5yr_bounded * 100.0, 2),
        linear_predictor=round(lp, 6),
        calibration_profile=profile_key,
        s0_2year=s0_2yr,
        s0_5year=s0_5yr,
        age_evaluated=eval_age,
        sex_evaluated=sex_str,
        male_code=male_code,
        egfr_evaluated=eval_egfr,
        uacr_evaluated=eval_uacr,
        applicability_status="VALID_ESTIMATE",
        message=(
            f"KFRE {profile_key} evaluation complete: 2-year kidney failure risk = "
            f"{r_2yr_bounded * 100.0:.2f}%, 5-year risk = {r_5yr_bounded * 100.0:.2f}%."
        ),
        disclaimer=KFRE_DISCLAIMER,
        validation_errors=[],
    )
