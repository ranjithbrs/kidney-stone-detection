"""NEFROAI-X Clinical Calculation & Staging Module.

Provides clinical algorithms for:
- eGFR Calculation (CKD-EPI 2021 race-free creatinine equation)
- KDIGO GFR Categories (G1 to G5)
- KDIGO Albuminuria Categories (A1 to A3)
- KDIGO CGA Staging and Composite Risk Matrix
"""

from src.clinical.egfr_calculator import (
    calculate_egfr_ckd_epi_2021,
    calculate_egfr_vectorized,
    decode_sex,
)
from src.clinical.kdigo_staging import (
    ALBUMINURIA_CATEGORIES,
    CHRONICITY_DISCLAIMER,
    GFR_CATEGORIES,
    KDIGO_RISK_MATRIX,
    classify_albuminuria_category,
    classify_gfr_category,
    classify_kdigo_composite_risk,
)

__all__ = [
    "calculate_egfr_ckd_epi_2021",
    "calculate_egfr_vectorized",
    "decode_sex",
    "classify_gfr_category",
    "classify_albuminuria_category",
    "classify_kdigo_composite_risk",
    "GFR_CATEGORIES",
    "ALBUMINURIA_CATEGORIES",
    "KDIGO_RISK_MATRIX",
    "CHRONICITY_DISCLAIMER",
]
