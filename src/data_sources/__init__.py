"""Data sources package for clinical datasets and external cohorts.
"""

from src.data_sources.nhanes_loader import (
    OFFICIAL_NHANES_URLS,
    STANDARDIZED_FEATURE_MAPPING,
    calculate_adult_severity_cohort,
    compute_sha256,
    download_nhanes_files,
    extract_harmonized_ckd_features,
    generate_nhanes_data_quality_report,
    load_nhanes_2017_2018,
    load_nhanes_file,
    merge_nhanes_components,
    validate_nhanes_source_schema,
    verify_uacr_agreement,
)

__all__ = [
    "OFFICIAL_NHANES_URLS",
    "STANDARDIZED_FEATURE_MAPPING",
    "calculate_adult_severity_cohort",
    "compute_sha256",
    "download_nhanes_files",
    "extract_harmonized_ckd_features",
    "generate_nhanes_data_quality_report",
    "load_nhanes_2017_2018",
    "load_nhanes_file",
    "merge_nhanes_components",
    "validate_nhanes_source_schema",
    "verify_uacr_agreement",
]
