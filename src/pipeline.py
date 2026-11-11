"""
Phase 9 / Phase 4 Step 2: End-to-End Clinical Diagnostic Pipeline
Combines:
1. Strict schema validation (rejects incompatible/non-renal datasets)
2. Safe clinical sanitization (feature-specific unit conversion, explicit missingness tracking, NO silent healthy defaults)
3. Biological plausibility validation (NO silent clamping; preserves genuine clinical extremes; flags invalid values)
4. Mandatory critical biomarker gate (abstains if sc, al, or hemo is missing, unsupported, or invalid)
5. Fitted Preprocessing (Median/Mode imputation for non-critical features, Standard Scaling)
6. Feature Selection (Top-10 consensus biomarkers)
7. Trained Champion Model (Random Forest Classifier)
8. Explainability Layer (Feature Contribution weights)
Supports single-record and batch inference, self-contained save and load.
"""

import os
import re
import joblib
import numpy as np
import pandas as pd


# Core clinical schema constants
CRITICAL_FEATURES = ['sc', 'al', 'hemo']
CANONICAL_24_FEATURES = [
    'age', 'bp', 'sg', 'al', 'su', 'bgr', 'bu', 'sc', 'sod', 'pot',
    'hemo', 'pcv', 'wc', 'rc', 'rbc', 'pc', 'pcc', 'ba', 'htn', 'dm',
    'cad', 'appet', 'pe', 'ane'
]
TOP_10_CONSENSUS_FEATURES = ['hemo', 'sg', 'pcv', 'rc', 'al', 'htn', 'sc', 'bu', 'dm', 'bgr']
CORE_RENAL_BIOMARKERS = {'hemo', 'sc', 'al', 'sg', 'bu', 'bgr', 'pcv', 'rc', 'bp', 'sod', 'pot'}
PERMISSIBLE_METADATA_COLS = {
    'id', 'unnamed: 0', 'patient_id', 'uid', 'sample_id', 'subject_id',
    'name', 'timestamp', 'date', 'classification', 'class', 'target'
}
KNOWN_INCOMPATIBLE_SIGNATURES = [
    {'gravity', 'ph', 'osmo', 'cond', 'calc'},
    {'treatment', 'stone_size', 'success'}
]

# Validated clinical unit conversions per feature.
# Only feature-specific conversions with unambiguous mathematical mappings are supported.
# Unsupported or incompatible units are rejected rather than silently stripped.
VALIDATED_UNIT_CONVERSIONS = {
    # Serum Creatinine: canonical mg/dL.
    # Standard SI unit: µmol/L (1 mg/dL = 88.42 µmol/L).
    "sc": {
        "canonical": "mg/dL",
        "units": {
            "": 1.0,
            "mg/dl": 1.0,
            "mg/dl.": 1.0,
            "umol/l": 1.0 / 88.42,
            "µmol/l": 1.0 / 88.42,
            "micromol/l": 1.0 / 88.42,
            "mcmol/l": 1.0 / 88.42
        }
    },
    # Hemoglobin: canonical g/dL.
    # Standard SI unit in Europe/UK: g/L (1 g/dL = 10.0 g/L).
    "hemo": {
        "canonical": "g/dL",
        "units": {
            "": 1.0,
            "g/dl": 1.0,
            "g/dl.": 1.0,
            "g/l": 1.0 / 10.0,
            "g/l.": 1.0 / 10.0
        }
    },
    # Blood Glucose Random: canonical mg/dL.
    # Standard SI unit: mmol/L (1 mmol/L = 18.0182 mg/dL).
    "bgr": {
        "canonical": "mg/dL",
        "units": {
            "": 1.0,
            "mg/dl": 1.0,
            "mg/dl.": 1.0,
            "mmol/l": 18.0182,
            "mmol/l.": 18.0182
        }
    },
    # Packed Cell Volume / Hematocrit: canonical %.
    "pcv": {
        "canonical": "%",
        "units": {
            "": 1.0,
            "%": 1.0,
            "vol%": 1.0
        }
    },
    # Red Blood Cell Count: canonical M/mcL (millions/mcL).
    "rc": {
        "canonical": "M/mcL",
        "units": {
            "": 1.0,
            "m/mcl": 1.0,
            "m/ul": 1.0,
            "millions/mcl": 1.0,
            "10^6/ul": 1.0,
            "10^12/l": 1.0
        }
    },
    # Blood Urea: canonical mg/dL.
    # Note: mmol/L is rejected for whole blood urea because BUN vs Whole Urea conversion differs by factor of 2.14.
    "bu": {
        "canonical": "mg/dL",
        "units": {
            "": 1.0,
            "mg/dl": 1.0
        }
    },
    # Blood Pressure: canonical mmHg.
    "bp": {
        "canonical": "mmHg",
        "units": {
            "": 1.0,
            "mmhg": 1.0
        }
    },
    # Patient Age: canonical years.
    "age": {
        "canonical": "years",
        "units": {
            "": 1.0,
            "years": 1.0,
            "yrs": 1.0,
            "yo": 1.0,
            "y": 1.0
        }
    },
    # Serum Sodium: canonical mEq/L (or mmol/L for monovalent ion).
    "sod": {
        "canonical": "mEq/L",
        "units": {
            "": 1.0,
            "meq/l": 1.0,
            "mmol/l": 1.0
        }
    },
    # Serum Potassium: canonical mEq/L (or mmol/L for monovalent ion).
    "pot": {
        "canonical": "mEq/L",
        "units": {
            "": 1.0,
            "meq/l": 1.0,
            "mmol/l": 1.0
        }
    },
    # White Blood Cell Count: canonical cells/mcL.
    "wc": {
        "canonical": "cells/mcL",
        "units": {
            "": 1.0,
            "cells/mcl": 1.0,
            "/mcl": 1.0,
            "/ul": 1.0,
            "cells/cumm": 1.0,
            "/cumm": 1.0
        }
    },
    # Specific Gravity: unitless ratio relative to water.
    "sg": {
        "canonical": "ratio",
        "units": {
            "": 1.0
        }
    },
    # Albumin dipstick grade: ordinal scale 0 to 5.
    "al": {
        "canonical": "grade",
        "units": {
            "": 1.0,
            "grade": 1.0
        }
    },
    # Urine Sugar dipstick grade: ordinal scale 0 to 5.
    "su": {
        "canonical": "grade",
        "units": {
            "": 1.0,
            "grade": 1.0
        }
    }
}

# 1. Physical Validity Constraints (Physical non-negativity and instrument scale constraints).
# Measurements violating these constraints represent mathematically or physically impossible values,
# instrument scale violations, or syntax corruption. They are flagged as INVALID_REPRESENTATION.
PHYSICAL_VALIDITY_CONSTRAINTS = {
    # Non-negative physiological concentrations / counts / pressures
    "sc": (0.0, None, "Serum creatinine concentration must be non-negative (mg/dL)"),
    "hemo": (0.0, None, "Hemoglobin concentration must be non-negative (g/dL)"),
    "bgr": (0.0, None, "Blood glucose concentration must be non-negative (mg/dL)"),
    "bu": (0.0, None, "Blood urea concentration must be non-negative (mg/dL)"),
    "pcv": (0.0, 100.0, "Packed cell volume is a volume percentage and must be between 0% and 100%"),
    "rc": (0.0, None, "Red blood cell count must be non-negative (M/mcL)"),
    "wc": (0.0, None, "White blood cell count must be non-negative (cells/mcL)"),
    "sod": (0.0, None, "Serum sodium concentration must be non-negative (mEq/L)"),
    "pot": (0.0, None, "Serum potassium concentration must be non-negative (mEq/L)"),
    "bp": (0.0, None, "Systolic blood pressure must be non-negative (mmHg)"),
    "age": (0.0, 130.0, "Patient age must be non-negative and <= 130 years"),
    # Urine Specific Gravity: density relative to pure water (1.000) under standard conditions
    "sg": (1.000, None, "Urine specific gravity cannot be less than 1.000 (density of pure water)"),
    # Standardized clinical dipstick ordinal scales (strictly integer 0 to 5)
    "al": (0.0, 5.0, "Urinary albumin dipstick grade must be on the standardized 0-5 scale"),
    "su": (0.0, 5.0, "Urinary sugar dipstick grade must be on the standardized 0-5 scale")
}

# 2. Model-Validated Operating Domains.
# These boundaries define the operational envelope within which the machine learning model
# was trained, calibrated, and certified.
# PROVENANCE AND CLINICAL AI AUDIT NOTICE:
# - Training partition size: N_train = 320 records (80% stratified split of Dataset A, random_state=42).
# - Held-out test partition size: N_test = 80 records (20% stratified split).
# - Operating boundaries are derived from the training partition distribution (X_train) and explicit
#   engineering policy safeguards. They are NEVER derived from the held-out test partition.
# - If an empirical training boundary does not span all prospective clinical scenarios, the threshold
#   is explicitly designated as an ENGINEERING SAFEGUARD rather than an experimentally validated boundary.
# - Out-of-domain detection is a model-input safety decision, NOT a medical diagnosis.
#   It does NOT infer specific pathologies (e.g. hemorrhagic shock, rhabdomyolysis, dialysis indication,
#   HHS, uremic encephalopathy, or hypertensive emergency) from isolated laboratory analytes.
MODEL_VALIDATED_OPERATING_DOMAINS = {
    # Serum Creatinine (sc): Canonical mg/dL.
    # Training partition distribution (N=320): min=0.40, median=1.00, 99th percentile=19.16, max=48.10.
    # Operating domain: [0.2, 30.0] mg/dL.
    # Provenance: Training partition distribution with upper engineering safeguard (30.0 mg/dL).
    # Status: Engineering safeguard for linear risk screening calibration.
    "sc": (0.2, 30.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Hemoglobin (hemo): Canonical g/dL.
    # Training partition distribution (N=320): min=4.80, median=12.60, 99th percentile=17.65, max=17.80.
    # Operating domain: [2.5, 20.0] g/dL.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "hemo": (2.5, 20.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Urine Specific Gravity (sg): Canonical ratio relative to water.
    # Training partition distribution (N=320): discrete dipstick steps [1.005, 1.010, 1.015, 1.020, 1.025].
    # Operating domain: [1.002, 1.035].
    # Provenance: Training partition discrete values and routine refractometer/dipstick instrument policy.
    # Status: Instrument policy safeguard.
    "sg": (1.002, 1.035, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Urine Albumin Dipstick (al): Canonical ordinal grade 0 to 5.
    # Training partition distribution (N=320): min=0, max=5.
    # Operating domain: [0.0, 5.0].
    # Provenance: Standard clinical dipstick scale and training partition.
    # Status: Standardized instrument scale.
    "al": (0.0, 5.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Urine Sugar Dipstick (su): Canonical ordinal grade 0 to 5.
    # Training partition distribution (N=320): min=0, max=5.
    # Operating domain: [0.0, 5.0].
    # Provenance: Standard clinical dipstick scale and training partition.
    # Status: Standardized instrument scale.
    "su": (0.0, 5.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Blood Glucose Random (bgr): Canonical mg/dL.
    # Training partition distribution (N=320): min=22.00, median=121.00, 99th percentile=434.90, max=490.00.
    # Operating domain: [30.0, 600.0] mg/dL.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "bgr": (30.0, 600.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Blood Urea (bu): Canonical mg/dL.
    # Training partition distribution (N=320): min=1.50, median=42.00, 99th percentile=236.20, max=391.00.
    # Operating domain: [5.0, 400.0] mg/dL.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "bu": (5.0, 400.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Packed Cell Volume (pcv): Canonical %.
    # Training partition distribution (N=320): min=14.00, median=40.00, max=54.00.
    # Operating domain: [10.0, 65.0]%.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "pcv": (10.0, 65.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Red Blood Cell Count (rc): Canonical M/mcL.
    # Training partition distribution (N=320): min=2.10, median=4.80, max=8.00.
    # Operating domain: [1.5, 9.0] M/mcL.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "rc": (1.5, 9.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Systolic Blood Pressure (bp): Canonical mmHg.
    # Training partition distribution (N=320): min=50.00, median=80.00, max=140.00.
    # Operating domain: [40.0, 220.0] mmHg.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "bp": (40.0, 220.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Patient Age: Canonical years.
    # Training partition distribution (N=320): min=2.00, median=55.00, max=90.00.
    # Operating domain: [1.0, 105.0] years.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "age": (1.0, 105.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Serum Sodium (sod): Canonical mEq/L.
    # Training partition distribution (N=320): min=104.00, median=138.00, max=163.00.
    # Operating domain: [100.0, 180.0] mEq/L.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "sod": (100.0, 180.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # Serum Potassium (pot): Canonical mEq/L.
    # Training partition distribution (N=320): min=2.50, median=4.40, 99th percentile=6.59, max=47.00 (raw outlier).
    # Operating domain: [1.5, 10.0] mEq/L.
    # Provenance: Training partition distribution with outlier filtering safeguard.
    # Status: Engineering safeguard.
    "pot": (1.5, 10.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."),

    # White Blood Cell Count (wc): Canonical cells/mcL.
    # Training partition distribution (N=320): min=2200.00, median=8000.00, max=26400.00.
    # Operating domain: [1500.0, 40000.0] cells/mcL.
    # Provenance: Training partition distribution with engineering boundary safeguard.
    # Status: Engineering safeguard.
    "wc": (1500.0, 40000.0, "This measurement is outside the model's validated operating range. Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review.")
}

# Alias for backward compatibility
PHYSIOLOGICAL_VALIDITY_RANGES = MODEL_VALIDATED_OPERATING_DOMAINS


class KidneyDiagnosticPipeline:
    """
    Self-contained end-to-end clinical diagnostic pipeline with strict schema validation
    and patient safety abstention guards.
    """

    CRITICAL_FEATURES = CRITICAL_FEATURES
    CANONICAL_24_FEATURES = CANONICAL_24_FEATURES
    TOP_10_CONSENSUS_FEATURES = TOP_10_CONSENSUS_FEATURES
    CORE_RENAL_BIOMARKERS = CORE_RENAL_BIOMARKERS
    PERMISSIBLE_METADATA_COLS = PERMISSIBLE_METADATA_COLS
    KNOWN_INCOMPATIBLE_SIGNATURES = KNOWN_INCOMPATIBLE_SIGNATURES
    VALIDATED_UNIT_CONVERSIONS = VALIDATED_UNIT_CONVERSIONS
    PHYSICAL_VALIDITY_CONSTRAINTS = PHYSICAL_VALIDITY_CONSTRAINTS
    MODEL_VALIDATED_OPERATING_DOMAINS = MODEL_VALIDATED_OPERATING_DOMAINS
    PHYSIOLOGICAL_VALIDITY_RANGES = MODEL_VALIDATED_OPERATING_DOMAINS

    def __init__(self, preprocessor, model, selected_features, class_names=None):
        self.preprocessor = preprocessor
        self.model = model
        self.selected_features = selected_features
        self.class_names = class_names if class_names else {0: "Healthy / Normal", 1: "Kidney Disease / At Risk"}

        # Legacy bounds reference dictionary preserved for backward compatibility
        self.feature_bounds = {
            "age": (1.0, 110.0, 45.0),
            "bp": (40.0, 220.0, 80.0),
            "sg": (1.000, 1.050, 1.020),
            "al": (0.0, 5.0, 0.0),
            "su": (0.0, 5.0, 0.0),
            "bgr": (40.0, 600.0, 120.0),
            "bu": (5.0, 400.0, 40.0),
            "sc": (0.2, 25.0, 1.0),
            "sod": (90.0, 180.0, 138.0),
            "pot": (2.0, 12.0, 4.4),
            "hemo": (2.5, 20.0, 13.5),
            "pcv": (10.0, 60.0, 40.0),
            "wc": (1500.0, 30000.0, 7800.0),
            "rc": (1.5, 9.0, 4.8)
        }

    @classmethod
    def validate_schema(cls, data):
        """
        Validates whether incoming data conforms to the clinical CKD schema.
        Rejects non-renal datasets (e.g. kidney stone urinalysis, surgical cohorts)
        and malformed or empty inputs.

        Returns:
            is_valid (bool): True if schema is compatible with CKD inference.
            reason (str): Validation description or descriptive rejection rationale.
        """
        if data is None:
            return False, "Schema Validation Error: Input data is None."

        if isinstance(data, dict):
            keys = [str(k).lower().strip() for k in data.keys()]
            feature_keys = [k for k in keys if k not in cls.PERMISSIBLE_METADATA_COLS]
            if not feature_keys:
                return False, "Schema Validation Error: Input record contains no clinical feature measurements (empty or metadata only)."

            key_set = set(feature_keys)
            for sig in cls.KNOWN_INCOMPATIBLE_SIGNATURES:
                if len(sig & key_set) >= 2:
                    return False, (
                        f"Schema Validation Error: Incompatible dataset schema detected: "
                        f"Contains non-renal biomarkers {sorted(list(sig & key_set))} matching kidney stone / surgical cohort."
                    )

            ckd_overlap = key_set & set(cls.CANONICAL_24_FEATURES)
            if not ckd_overlap:
                return False, (
                    f"Schema Validation Error: None of the provided features {sorted(list(key_set))} "
                    f"match recognized CKD clinical features."
                )

            core_overlap = key_set & cls.CORE_RENAL_BIOMARKERS
            if not core_overlap:
                return False, (
                    f"Schema Validation Error: Record lacks core renal biomarkers "
                    f"(expected at least one of {sorted(list(cls.CORE_RENAL_BIOMARKERS))})."
                )

            return True, "Valid CKD schema."

        if isinstance(data, pd.DataFrame):
            if data.empty:
                return False, "Schema Validation Error: DataFrame is empty."

            cols = [str(c).lower().strip() for c in data.columns]
            feature_cols = [c for c in cols if c not in cls.PERMISSIBLE_METADATA_COLS]
            if not feature_cols:
                return False, "Schema Validation Error: DataFrame contains no clinical feature columns."

            col_set = set(feature_cols)
            for sig in cls.KNOWN_INCOMPATIBLE_SIGNATURES:
                if len(sig & col_set) >= 2:
                    return False, (
                        f"Schema Validation Error: Incompatible dataset schema detected: "
                        f"Contains non-renal columns {sorted(list(sig & col_set))} matching kidney stone / surgical cohort."
                    )

            ckd_overlap = col_set & set(cls.CANONICAL_24_FEATURES)
            if not ckd_overlap:
                return False, (
                    f"Schema Validation Error: None of the DataFrame columns match recognized CKD clinical features."
                )

            core_overlap = col_set & cls.CORE_RENAL_BIOMARKERS
            if not core_overlap:
                return False, (
                    f"Schema Validation Error: DataFrame lacks core renal biomarkers."
                )

            return True, "Valid CKD schema."

        if isinstance(data, list):
            if len(data) == 0:
                return False, "Schema Validation Error: Empty record list."
            if isinstance(data[0], dict):
                return cls.validate_schema(pd.DataFrame(data))
            return False, "Schema Validation Error: Invalid record list format."

        return False, f"Schema Validation Error: Unsupported input type: {type(data).__name__}"

    def _parse_and_validate_numerical_feature(self, feat, raw_val):
        """
        Parses numerical clinical measurement:
        - Validates feature-specific units (rejects unsupported/ambiguous units).
        - Executes mathematically validated unit conversions (e.g. µmol/L -> mg/dL, g/L -> g/dL, mmol/L -> mg/dL).
        - Validates physical validity constraints (physical non-negativity, dipstick instrument scale limits).
        - Validates against model-validated empirical operating domains (derived from Dataset A training distribution).
        - Preserves genuine clinical extreme values without silent clamping or data alteration.

        Returns:
            (converted_val, status, message)
            status:
                "VALID"                  : In-domain valid measurement
                "OUT_OF_DOMAIN"          : Genuine clinical extreme exceeding validated model domain (converted_val PRESERVED)
                "INVALID_REPRESENTATION" : Unphysical / invalid numerical representation (converted_val is None)
                "UNSUPPORTED_UNIT"       : Unsupported unit string (converted_val is None)
                "UNPARSEABLE"            : Corrupted / non-numeric string (converted_val is None)
                "MISSING"                : Empty, None, or null indicator (converted_val is None)
        """
        if raw_val is None:
            return None, "MISSING", "Measurement is None"

        s = str(raw_val).strip().replace('\t', '')
        if s in ["", "?", "nan", "NaN", "None", "null", "none"]:
            return None, "MISSING", "Measurement is empty/null"

        # Regex match number part and optional unit suffix
        m = re.match(r'^([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(.*)$', s)
        if not m:
            return None, "UNPARSEABLE", f"Cannot parse numerical measurement from '{s}'"

        num_str, unit_str = m.group(1), m.group(2).strip().lower()
        try:
            raw_num = float(num_str)
        except (ValueError, TypeError):
            return None, "UNPARSEABLE", f"Invalid floating-point string '{num_str}'"

        if np.isnan(raw_num) or np.isinf(raw_num):
            return None, "INVALID_REPRESENTATION", f"Numerical value is NaN or Inf"

        # Check feature-specific unit configuration
        spec = self.VALIDATED_UNIT_CONVERSIONS.get(feat, {"canonical": "", "units": {"": 1.0}})
        allowed_units = spec["units"]

        if unit_str not in allowed_units:
            return None, "UNSUPPORTED_UNIT", (
                f"Unsupported/ambiguous unit '{unit_str}' for feature '{feat}'. "
                f"Expected canonical {spec['canonical']} or validated equivalents: {list(allowed_units.keys())}."
            )

        # Convert to canonical model unit
        conversion_factor = allowed_units[unit_str]
        converted_val = raw_num * conversion_factor

        # Clean float rounding
        if feat == "sc":
            converted_val = round(converted_val, 3)
        elif feat in ["hemo", "bgr"]:
            converted_val = round(converted_val, 2)

        # 1. Physical Validity Constraints (Non-negativity, dipstick instrument scale)
        # Violations represent invalid numerical representations / physical impossibilities
        if feat in self.PHYSICAL_VALIDITY_CONSTRAINTS:
            min_phys, max_phys, phys_desc = self.PHYSICAL_VALIDITY_CONSTRAINTS[feat]
            if min_phys is not None and converted_val < min_phys:
                return None, "INVALID_REPRESENTATION", (
                    f"Measurement {converted_val} is an invalid representation: {phys_desc}."
                )
            if max_phys is not None and converted_val > max_phys:
                return None, "INVALID_REPRESENTATION", (
                    f"Measurement {converted_val} is an invalid representation: {phys_desc}."
                )

        # 2. Model-Validated Operating Domain (Empirical training distribution)
        # Genuine clinical measurements outside this envelope are preserved as converted_val!
        if feat in self.MODEL_VALIDATED_OPERATING_DOMAINS:
            low_domain, high_domain, domain_desc = self.MODEL_VALIDATED_OPERATING_DOMAINS[feat]
            if converted_val < low_domain or converted_val > high_domain:
                return converted_val, "OUT_OF_DOMAIN", (
                    f"Measurement {converted_val} {spec['canonical']} is outside the model's validated "
                    f"operating domain ({low_domain} - {high_domain} {spec['canonical']}). {domain_desc}"
                )

        return converted_val, "VALID", f"Valid in-domain measurement in {spec['canonical']}"

    def _sanitize_and_inspect_record(self, raw_record):
        """
        Sanitizes raw record and computes explicit missingness, invalidity, and out-of-domain metadata.
        CRITICAL SAFETY RULES:
        1. Missing values are marked as np.nan and NEVER defaulted to healthy values.
        2. Valid clinical measurements are NEVER silently clamped. Genuine extremes are preserved.
        3. Extreme out-of-domain measurements are PRESERVED in clean_record, NEVER silently replaced with medians.
        4. Median/mode imputation is strictly reserved for missing/omitted measurements.
        5. Unsupported units or invalid representations are explicitly flagged as invalid.
        """
        if not isinstance(raw_record, dict):
            raw_record = {}

        sanitized = {}
        all_expected = getattr(self.preprocessor, "feature_names", CANONICAL_24_FEATURES)
        target_features = self.selected_features
        num_cols = getattr(self.preprocessor, "num_cols", [f for f in all_expected if f in self.feature_bounds])
        cat_cols = getattr(self.preprocessor, "cat_cols", [f for f in all_expected if f not in num_cols])

        valid_features = []
        valid_canonical_24 = []
        missing_features = []
        critical_missing = []
        out_of_domain_features = []
        invalid_features = []
        feature_anomalies = {}

        for feat in all_expected:
            raw_val = raw_record.get(feat, None)

            # Numerical feature processing with validated unit parsing and biological bounds
            if feat in num_cols:
                parsed_val, status, reason = self._parse_and_validate_numerical_feature(feat, raw_val)

                if status == "VALID":
                    sanitized[feat] = parsed_val
                    valid_canonical_24.append(feat)
                    if feat in target_features:
                        valid_features.append(feat)

                elif status == "OUT_OF_DOMAIN":
                    # CRITICAL: Preserve genuine clinical measurement! Do NOT replace with np.nan or median!
                    sanitized[feat] = parsed_val
                    out_of_domain_features.append(feat)
                    valid_canonical_24.append(feat)
                    if feat in target_features:
                        valid_features.append(feat)
                    feature_anomalies[feat] = {
                        "raw_value": raw_val,
                        "status": status,
                        "reason": reason,
                        "preserved_value": parsed_val
                    }

                elif status == "MISSING":
                    sanitized[feat] = np.nan
                    feature_anomalies[feat] = {
                        "raw_value": raw_val,
                        "status": status,
                        "reason": reason
                    }
                    if feat in target_features:
                        missing_features.append(feat)
                        if feat in self.CRITICAL_FEATURES:
                            critical_missing.append(feat)

                else:  # "INVALID_REPRESENTATION", "UNSUPPORTED_UNIT", "UNPARSEABLE"
                    sanitized[feat] = np.nan
                    invalid_features.append(feat)
                    feature_anomalies[feat] = {
                        "raw_value": raw_val,
                        "status": status,
                        "reason": reason
                    }
                    if feat in target_features:
                        missing_features.append(feat)
                        if feat in self.CRITICAL_FEATURES:
                            critical_missing.append(feat)

            else:
                # Categorical field processing & synonym mapping
                if raw_val is None or str(raw_val).strip() in ["", "?", "nan", "NaN", "None", "null", "none"]:
                    sanitized[feat] = np.nan
                    feature_anomalies[feat] = {"raw_value": raw_val, "status": "MISSING", "reason": "Categorical value missing"}
                    if feat in target_features:
                        missing_features.append(feat)
                        if feat in self.CRITICAL_FEATURES:
                            critical_missing.append(feat)
                    continue

                cat_val = str(raw_val).strip().lower().replace('\t', '')
                if cat_val in ["1", "true", "t", "yes", "y", "present"]:
                    cat_val = "yes" if feat in ["htn", "dm", "cad", "pe", "ane"] else "present"
                    sanitized[feat] = cat_val
                    valid_canonical_24.append(feat)
                    if feat in target_features:
                        valid_features.append(feat)
                elif cat_val in ["0", "false", "f", "no", "n", "notpresent", "absent"]:
                    cat_val = "no" if feat in ["htn", "dm", "cad", "pe", "ane"] else "notpresent"
                    sanitized[feat] = cat_val
                    valid_canonical_24.append(feat)
                    if feat in target_features:
                        valid_features.append(feat)
                elif cat_val in ["normal", "abnormal"]:
                    sanitized[feat] = cat_val
                    valid_canonical_24.append(feat)
                    if feat in target_features:
                        valid_features.append(feat)
                elif cat_val in ["good", "poor"]:
                    sanitized[feat] = cat_val
                    valid_canonical_24.append(feat)
                    if feat in target_features:
                        valid_features.append(feat)
                else:
                    sanitized[feat] = np.nan
                    invalid_features.append(feat)
                    feature_anomalies[feat] = {"raw_value": raw_val, "status": "UNRECOGNIZED_CATEGORY", "reason": f"Unrecognized category '{cat_val}'"}
                    if feat in target_features:
                        missing_features.append(feat)
                        if feat in self.CRITICAL_FEATURES:
                            critical_missing.append(feat)

        total_target = len(target_features)
        completeness_ratio = round(len(valid_features) / total_target, 4) if total_target > 0 else 0.0
        full_panel_completeness = round(len(valid_canonical_24) / len(all_expected), 4) if len(all_expected) > 0 else 0.0
        # Imputed features are strictly missing/omitted non-critical features. Never out-of-domain or invalid features!
        imputed_features = [f for f in missing_features if f not in critical_missing and f not in invalid_features and f not in out_of_domain_features]

        meta = {
            "valid_features": valid_features,
            "valid_canonical_24": valid_canonical_24,
            "missing_features": missing_features,
            "critical_missing": critical_missing,
            "out_of_domain_features": list(dict.fromkeys(out_of_domain_features)),
            "invalid_features": list(dict.fromkeys(invalid_features)),
            "imputed_features": imputed_features,
            "data_completeness_ratio": completeness_ratio,
            "full_panel_completeness_ratio": full_panel_completeness,
            "feature_anomalies": feature_anomalies
        }

        return sanitized, meta

        return sanitized, meta

    def _validate_and_sanitize_record(self, raw_record):
        """
        Backward-compatible sanitation helper.
        Returns sanitized feature dict with missing/invalid values represented as np.nan.
        """
        sanitized, _ = self._sanitize_and_inspect_record(raw_record)
        return sanitized

    def generate_clinical_report(self, patient_dict, result=None):
        """
        Generates a standard clinical diagnostic text report.
        Accurately discloses completeness ratio, missing/imputed biomarkers, and abstention notices.
        """
        if result is None:
            result = self.predict_single(patient_dict, include_attributions=True)

        report = f"""================================================================================
                    NEFROAI CLINICAL DIAGNOSTIC EVALUATION
================================================================================
Timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
System: NefroAI Clinical Decision Support System (IEEE Access Framework)
Champion Model: {type(self.model).__name__} (5-Fold Stratified Tuned)

1. PATIENT LABORATORY PARAMETERS:
--------------------------------------------------------------------------------
"""
        for k in self.selected_features:
            val = patient_dict.get(k, result.get('sanitized_inputs', {}).get(k, 'MISSING'))
            report += f"- {k:<6}: {val}\n"

        status = result.get("prediction_status", "UNKNOWN")

        if status.startswith("ABSTAIN") or status.startswith("REJECTED"):
            report += f"""
2. DIAGNOSTIC ASSESSMENT & CLINICAL SAFETY STATUS:
--------------------------------------------------------------------------------
- Prediction Status:               {status}
- Diagnostic Evaluation:           {result.get('diagnosis', 'PREDICTION_WITHHELD')}
- Clinical Triage Tier:            {result.get('risk_category', 'Abstained')}
- Model Consensus Completeness:    {result.get('data_completeness_ratio', 0.0)*100:.1f}% (Top-10 Consensus Features)
- Full Panel Completeness:         {result.get('full_panel_completeness_ratio', 0.0)*100:.1f}% (Full 24-Analyte Panel)
- Missing / Invalid Biomarkers:    {result.get('missing_features', [])}
- Safety Abstention Rationale:     {result.get('abstention_reason', 'N/A')}
"""
        else:
            prob_pct = f"{result['risk_probability']*100:.2f}%" if result.get('risk_probability') is not None else "N/A"
            conf_pct = f"{result['confidence_score']*100:.2f}%" if result.get('confidence_score') is not None else "N/A"
            report += f"""
2. DIAGNOSTIC ASSESSMENT & RISK SCORE:
--------------------------------------------------------------------------------
- Prediction Status:               {status}
- Diagnostic Class:                {result.get('diagnosis')}
- Calibrated Disease Probability:  {prob_pct}
- Clinical Triage Tier:            {result.get('risk_category')}
- Model Confidence:                {conf_pct}
- Model Consensus Completeness:    {result.get('data_completeness_ratio', 1.0)*100:.1f}% (Top-10 Features)
- Full Panel Completeness:         {result.get('full_panel_completeness_ratio', 1.0)*100:.1f}% (24 Features)
"""
            if result.get("imputed_features"):
                report += f"- Imputed Non-Critical Features:   {result['imputed_features']} (Fitted training medians/modes; no refitting)\n"

            if "feature_attributions" in result:
                report += """
3. EXPLAINABLE AI (XAI) ATTRIBUTIONS:
--------------------------------------------------------------------------------
Top risk contributors identified by feature leverage weights:
"""
                for k, v in result["feature_attributions"].items():
                    report += f"- {k:<6}: Importance Weight = {v['importance_weight']:.4f} (Normalized = {v['normalized_value']:+.2f})\n"

        report += """
================================================================================
DISCLAIMER: This report is generated by a Clinical Decision Support System
(CDSS) for investigational and triaging assistance. Final clinical judgment
and therapeutic regimens must be verified by a board-certified physician.
================================================================================
"""
        return report

    def predict_single(self, patient_dict, include_attributions=True, raise_on_invalid_schema=False):
        """
        Executes end-to-end prediction for a single patient with safety abstention guards.

        Returns a result dictionary with:
            - input_valid (bool)
            - prediction_status ('PREDICTION_AVAILABLE', 'INCOMPLETE_INPUT_ESTIMATE',
                                 'ABSTAIN_MISSING_CRITICAL_FEATURES', 'REJECTED_INVALID_SCHEMA')
            - diagnostic_class (0, 1, or None)
            - diagnosis (str)
            - risk_probability (float or None)
            - confidence_score (float or None)
            - risk_category (str)
            - abstention_reason (str or None)
            - data_completeness_ratio (float)
            - full_panel_completeness_ratio (float)
            - missing_features (list)
            - imputed_features (list)
            - sanitized_inputs (dict)
            - feature_anomalies (dict)
            - feature_attributions (dict, optional)
        """
        # Step 0: Check overall schema validity
        is_schema_valid, schema_reason = self.validate_schema(patient_dict)
        if not is_schema_valid:
            if raise_on_invalid_schema:
                raise ValueError(schema_reason)
            return {
                "input_valid": False,
                "prediction_status": "REJECTED_INVALID_SCHEMA",
                "diagnostic_class": None,
                "diagnosis": "REJECTED (Invalid or Incompatible Schema)",
                "risk_probability": None,
                "confidence_score": None,
                "risk_category": "Rejected (Incompatible Schema)",
                "abstention_reason": schema_reason,
                "data_completeness_ratio": 0.0,
                "full_panel_completeness_ratio": 0.0,
                "missing_features": list(self.selected_features),
                "imputed_features": [],
                "sanitized_inputs": {},
                "feature_anomalies": {}
            }

        # Step 1: Sanitize, inspect units, and validate physiological ranges
        clean_record, meta = self._sanitize_and_inspect_record(patient_dict)

        # Step 2: Check Critical Biomarkers Gate (sc, al, hemo)
        if meta["critical_missing"]:
            reasons = []
            for crit in meta["critical_missing"]:
                anomaly = meta["feature_anomalies"].get(crit)
                if anomaly:
                    reasons.append(f"{crit}: {anomaly['reason']}")
                else:
                    reasons.append(f"{crit}: missing measurement")

            crit_names = {"sc": "Serum Creatinine (sc)", "al": "Urine Albumin (al)", "hemo": "Hemoglobin (hemo)"}
            crit_desc = [crit_names.get(f, f) for f in meta["critical_missing"]]
            abstain_msg = (
                f"Automated prediction withheld: Critical biomarker safety failure in {meta['critical_missing']} "
                f"({', '.join(crit_desc)}). Details: {'; '.join(reasons)}. "
                f"Clinical protocol requires valid, in-domain measurements for Serum Creatinine, Urine Albumin, and Hemoglobin."
            )
            return {
                "input_valid": True,
                "prediction_status": "ABSTAIN_MISSING_CRITICAL_FEATURES",
                "diagnostic_class": None,
                "diagnosis": "PREDICTION_WITHHELD (Missing or Invalid Critical Lab Tests)",
                "risk_probability": None,
                "confidence_score": None,
                "risk_category": "Abstained (Incomplete Critical Labs)",
                "abstention_reason": abstain_msg,
                "data_completeness_ratio": meta["data_completeness_ratio"],
                "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
                "missing_features": meta["missing_features"],
                "imputed_features": [],
                "sanitized_inputs": {k: clean_record[k] for k in self.selected_features if k in clean_record and not pd.isna(clean_record[k])},
                "feature_anomalies": meta["feature_anomalies"]
            }

        # Step 3: Check Invalid Numerical Representations Gate on Target Features
        target_invalids = [f for f in meta["invalid_features"] if f in self.selected_features]
        if target_invalids:
            reasons = [f"{f}: {meta['feature_anomalies'][f]['reason']}" for f in target_invalids]
            abstain_msg = (
                f"Automated prediction withheld: Invalid numerical representation or unsupported format in {target_invalids}. "
                f"Details: {'; '.join(reasons)}. "
                f"Corrupted, non-numeric, or unphysical inputs cannot be safely processed or imputed."
            )
            return {
                "input_valid": False,
                "prediction_status": "ABSTAIN_INVALID_INPUT_MEASUREMENT",
                "diagnostic_class": None,
                "diagnosis": "PREDICTION_WITHHELD (Invalid Numerical Input)",
                "risk_probability": None,
                "confidence_score": None,
                "risk_category": "Abstained (Invalid Measurement)",
                "abstention_reason": abstain_msg,
                "data_completeness_ratio": meta["data_completeness_ratio"],
                "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
                "missing_features": meta["missing_features"],
                "imputed_features": [],
                "sanitized_inputs": {k: clean_record[k] for k in self.selected_features if k in clean_record and not pd.isna(clean_record[k])},
                "feature_anomalies": meta["feature_anomalies"]
            }

        # Step 4: Check Model-Validated Operating Domain Gate (Out-of-Domain Measurements)
        target_ood = [f for f in meta["out_of_domain_features"] if f in self.selected_features]
        if target_ood:
            ood_reasons = [f"{f}: {meta['feature_anomalies'][f]['reason']}" for f in target_ood]
            abstain_msg = (
                f"Automated prediction withheld: Clinical measurement(s) in {target_ood} exceed the model's "
                f"validated operating domain. Details: {'; '.join(ood_reasons)}. "
                f"This measurement is outside the model's validated operating range. Automated prediction has been withheld. "
                f"Verify the laboratory measurement and obtain qualified clinical review."
            )
            return {
                "input_valid": True,
                "prediction_status": "ABSTAIN_OUT_OF_DOMAIN_MEASUREMENT",
                "diagnostic_class": None,
                "diagnosis": "PREDICTION_WITHHELD (Out-of-Domain Measurement)",
                "risk_probability": None,
                "confidence_score": None,
                "risk_category": "Abstained (Out-of-Domain Measurement)",
                "abstention_reason": abstain_msg,
                "data_completeness_ratio": meta["data_completeness_ratio"],
                "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
                "missing_features": meta["missing_features"],
                "imputed_features": [],
                "out_of_domain_features": meta["out_of_domain_features"],
                "sanitized_inputs": {k: clean_record[k] for k in self.selected_features if k in clean_record and not pd.isna(clean_record[k])},
                "feature_anomalies": meta["feature_anomalies"]
            }

        # Step 5: Preprocess via fitted training imputer & scaler (NO refitting on incoming data)
        transformed_df = self.preprocessor.transform_single_record(clean_record)
        X_selected = transformed_df[self.selected_features]

        # Step 6: Model Inference
        pred_class = int(self.model.predict(X_selected)[0])
        probabilities = self.model.predict_proba(X_selected)[0]
        risk_prob = float(probabilities[1])

        # Step 7: Clinical Triage Risk Category
        if risk_prob < 0.25:
            risk_category = "Low Risk (Normal)"
        elif risk_prob < 0.50:
            risk_category = "Moderate Risk (Observation Suggested)"
        elif risk_prob < 0.80:
            risk_category = "High Risk (Clinical Evaluation Recommended)"
        else:
            risk_category = "Critical Risk (Urgent Nephrology Consultation Required)"

        # Step 8: Prediction Status determination
        if meta["missing_features"]:
            prediction_status = "INCOMPLETE_INPUT_ESTIMATE"
        else:
            prediction_status = "PREDICTION_AVAILABLE"

        result = {
            "input_valid": True,
            "prediction_status": prediction_status,
            "diagnostic_class": pred_class,
            "diagnosis": self.class_names.get(pred_class, str(pred_class)),
            "risk_probability": round(risk_prob, 4),
            "confidence_score": round(float(np.max(probabilities)), 4),
            "risk_category": risk_category,
            "abstention_reason": None,
            "data_completeness_ratio": meta["data_completeness_ratio"],
            "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
            "missing_features": meta["missing_features"],
            "imputed_features": meta["imputed_features"],
            "sanitized_inputs": {k: clean_record[k] for k in self.selected_features if k in clean_record and not pd.isna(clean_record[k])},
            "feature_anomalies": meta["feature_anomalies"]
        }

        # Step 9: Feature Attribution Calculation
        if include_attributions and hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            feature_impacts = {}
            for feat, imp in zip(self.selected_features, importances):
                val = float(X_selected[feat].iloc[0])
                feature_impacts[feat] = {
                    "importance_weight": round(float(imp), 4),
                    "normalized_value": round(val, 3)
                }
            result["feature_attributions"] = feature_impacts

        return result

    def predict_batch(self, df_or_records, raise_on_invalid_schema=True):
        """
        Batch prediction for multiple patient records with dataset-level schema validation
        and row-level safety tracking.
        """
        if df_or_records is None:
            return pd.DataFrame()
        if isinstance(df_or_records, list):
            if len(df_or_records) == 0:
                return pd.DataFrame()
            df = pd.DataFrame(df_or_records)
        else:
            df = df_or_records
        if len(df) == 0:
            return pd.DataFrame()

        # Step 0: Validate overall dataset schema
        is_schema_valid, schema_reason = self.validate_schema(df)
        if not is_schema_valid:
            if raise_on_invalid_schema:
                raise ValueError(schema_reason)
            return pd.DataFrame([{
                "input_valid": False,
                "prediction_status": "REJECTED_INVALID_SCHEMA",
                "diagnostic_class": None,
                "diagnosis": "REJECTED (Invalid or Incompatible Schema)",
                "risk_probability": None,
                "risk_category": "Rejected (Incompatible Schema)",
                "data_completeness_ratio": 0.0,
                "full_panel_completeness_ratio": 0.0,
                "missing_features": list(self.selected_features),
                "imputed_features": [],
                "abstention_reason": schema_reason
            } for _ in range(len(df))])

        records = df.to_dict(orient="records")
        rows_meta = []
        clean_records = []
        inference_indices = []

        # Step 1: Inspect each row for missingness, invalid representations, and out-of-domain measurements
        for idx, rec in enumerate(records):
            clean_rec, meta = self._sanitize_and_inspect_record(rec)
            clean_records.append(clean_rec)
            rows_meta.append(meta)
            has_crit_missing = bool(meta["critical_missing"])
            has_target_invalid = bool(set(meta["invalid_features"]) & set(self.selected_features))
            has_target_ood = bool(set(meta["out_of_domain_features"]) & set(self.selected_features))
            if not has_crit_missing and not has_target_invalid and not has_target_ood:
                inference_indices.append(idx)

        # Step 2: Batch inference for rows that pass critical biomarker, validity, and in-domain gates
        predictions_map = {}
        if inference_indices:
            candidate_records = [clean_records[i] for i in inference_indices]
            df_candidates = pd.DataFrame(candidate_records)

            if hasattr(self.preprocessor, "transform_df"):
                transformed_df = self.preprocessor.transform_df(df_candidates)
            else:
                transformed_df = pd.concat(
                    [self.preprocessor.transform_single_record(r) for r in candidate_records],
                    ignore_index=True
                )

            X_selected = transformed_df[self.selected_features]
            preds = self.model.predict(X_selected)
            probs = self.model.predict_proba(X_selected)[:, 1]

            for orig_idx, pred, prob in zip(inference_indices, preds, probs):
                predictions_map[orig_idx] = (int(pred), float(prob))

        # Step 3: Assemble row-level outputs
        results = []
        for idx in range(len(records)):
            meta = rows_meta[idx]
            rec = records[idx]

            # Preserve metadata columns if present (e.g. id, patient_id)
            row_dict = {}
            for m_col in ["id", "patient_id", "uid", "sample_id", "subject_id"]:
                if m_col in rec:
                    row_dict[m_col] = rec[m_col]
                    break

            if meta["critical_missing"]:
                crit_names = {"sc": "Serum Creatinine (sc)", "al": "Urine Albumin (al)", "hemo": "Hemoglobin (hemo)"}
                crit_desc = [crit_names.get(f, f) for f in meta["critical_missing"]]
                row_dict.update({
                    "input_valid": True,
                    "prediction_status": "ABSTAIN_MISSING_CRITICAL_FEATURES",
                    "diagnostic_class": None,
                    "diagnosis": "PREDICTION_WITHHELD (Missing Critical Lab Tests)",
                    "risk_probability": None,
                    "risk_category": "Abstained (Incomplete Critical Labs)",
                    "data_completeness_ratio": meta["data_completeness_ratio"],
                    "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
                    "missing_features": meta["missing_features"],
                    "imputed_features": [],
                    "abstention_reason": (
                        f"Missing critical biomarker(s): {meta['critical_missing']} ({', '.join(crit_desc)})."
                    )
                })
            elif set(meta["invalid_features"]) & set(self.selected_features):
                invalids = sorted(list(set(meta["invalid_features"]) & set(self.selected_features)))
                row_dict.update({
                    "input_valid": False,
                    "prediction_status": "ABSTAIN_INVALID_INPUT_MEASUREMENT",
                    "diagnostic_class": None,
                    "diagnosis": "PREDICTION_WITHHELD (Invalid Numerical Input)",
                    "risk_probability": None,
                    "risk_category": "Abstained (Invalid Measurement)",
                    "data_completeness_ratio": meta["data_completeness_ratio"],
                    "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
                    "missing_features": meta["missing_features"],
                    "imputed_features": [],
                    "abstention_reason": f"Invalid numerical representation in {invalids}."
                })
            elif set(meta["out_of_domain_features"]) & set(self.selected_features):
                oods = sorted(list(set(meta["out_of_domain_features"]) & set(self.selected_features)))
                row_dict.update({
                    "input_valid": True,
                    "prediction_status": "ABSTAIN_OUT_OF_DOMAIN_MEASUREMENT",
                    "diagnostic_class": None,
                    "diagnosis": "PREDICTION_WITHHELD (Out-of-Domain Measurement)",
                    "risk_probability": None,
                    "risk_category": "Abstained (Out-of-Domain Measurement)",
                    "data_completeness_ratio": meta["data_completeness_ratio"],
                    "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
                    "missing_features": meta["missing_features"],
                    "imputed_features": [],
                    "abstention_reason": (
                        f"Clinical measurement(s) in {oods} exceed the model's validated operating domain. "
                        f"This measurement is outside the model's validated operating range. "
                        f"Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."
                    )
                })
            else:
                pred_cls, p = predictions_map[idx]
                if p < 0.25:
                    cat = "Low Risk (Normal)"
                elif p < 0.50:
                    cat = "Moderate Risk (Observation Suggested)"
                elif p < 0.80:
                    cat = "High Risk (Clinical Evaluation Recommended)"
                else:
                    cat = "Critical Risk (Urgent Nephrology Consultation Required)"

                status = "INCOMPLETE_INPUT_ESTIMATE" if meta["missing_features"] else "PREDICTION_AVAILABLE"

                row_dict.update({
                    "input_valid": True,
                    "prediction_status": status,
                    "diagnostic_class": pred_cls,
                    "diagnosis": self.class_names.get(pred_cls, str(pred_cls)),
                    "risk_probability": round(p, 4),
                    "risk_category": cat,
                    "data_completeness_ratio": meta["data_completeness_ratio"],
                    "full_panel_completeness_ratio": meta["full_panel_completeness_ratio"],
                    "missing_features": meta["missing_features"],
                    "imputed_features": meta["imputed_features"],
                    "abstention_reason": None
                })
            results.append(row_dict)

        return pd.DataFrame(results)

    def save(self, filepath="models/clinical_pipeline.joblib"):
        """Saves the complete pipeline to a single serialized file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(self, filepath)
        print(f"Pipeline successfully serialized to: {filepath}")

    @staticmethod
    def load(filepath="models/clinical_pipeline.joblib"):
        """Loads a pre-trained serialized pipeline."""
        import sys

        sys.modules.setdefault("pipeline", sys.modules[__name__])
        if "preprocessing" not in sys.modules:
            try:
                import src.preprocessing as _prep_mod
                sys.modules.setdefault("preprocessing", _prep_mod)
            except ImportError:
                import preprocessing  # noqa: F401
        return joblib.load(filepath)
