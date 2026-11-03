"""Reproducible NHANES 2017-2018 Downloader and Processing Pipeline.

Downloads official CDC/NCHS SAS Transport files for:
- DEMO_J: Demographic variables & survey weights
- BIOPRO_J: Standard biochemistry profile
- ALB_CR_J: Urine albumin & creatinine

Generates:
- datasets/external/nhanes_2017_2018/raw/*.xpt
- datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_merged.csv
- datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv
- datasets/external/nhanes_2017_2018/metadata/dataset_manifest.json
- datasets/external/nhanes_2017_2018/metadata/feature_mapping.json
- datasets/external/nhanes_2017_2018/metadata/data_quality_report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_sources.nhanes_loader import (
    STANDARDIZED_FEATURE_MAPPING,
    download_nhanes_files,
    extract_harmonized_ckd_features,
    generate_nhanes_data_quality_report,
    load_nhanes_2017_2018,
    merge_nhanes_components,
)

logger = logging.getLogger("download_nhanes_2017_2018")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def main():
    parser = argparse.ArgumentParser(description="Download and process official NHANES 2017-2018 datasets.")
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=str(PROJECT_ROOT / "datasets" / "external" / "nhanes_2017_2018" / "raw"),
        help="Target directory for raw .xpt files.",
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default=str(PROJECT_ROOT / "datasets" / "external" / "nhanes_2017_2018" / "processed"),
        help="Target directory for processed CSV files.",
    )
    parser.add_argument(
        "--metadata-dir",
        type=str,
        default=str(PROJECT_ROOT / "datasets" / "external" / "nhanes_2017_2018" / "metadata"),
        help="Target directory for metadata JSON files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if valid files already exist.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download step and proceed directly with existing raw files.",
    )

    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    processed_dir = Path(args.processed_dir)
    metadata_dir = Path(args.metadata_dir)

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("NEFROAI-X: Official NHANES 2017-2018 Ingestion Pipeline")
    print("=" * 70)

    # 1. Download
    manifest = {}
    if not args.skip_download:
        print("\n[Step 1/4] Downloading official SAS Transport files from CDC/NCHS...")
        manifest = download_nhanes_files(raw_dir, timeout=45, force=args.force)
        manifest_path = metadata_dir / "dataset_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"Manifest written to: {manifest_path}")

        # Check if all files downloaded or cached
        failed = [k for k, v in manifest.items() if v.get("status") == "failed"]
        if failed:
            print(f"\n[WARNING] Download failed for components: {failed}")
            for k in failed:
                print(f"  - {k}: {manifest[k].get('error')}")
            print("\nIf running inside a sandboxed environment without external network access,")
            print("please re-run with network permissions or execute outside the sandbox.")
            return 1
    else:
        print("\n[Step 1/4] Skipping download per user flag.")

    # 2. Ingestion & Validation
    print("\n[Step 2/4] Loading and validating raw SAS Transport files...")
    components = load_nhanes_2017_2018(raw_dir)
    for k, df in components.items():
        print(f"  - Loaded {k.upper()}: {df.shape[0]} rows, {df.shape[1]} columns, {df['SEQN'].nunique()} unique SEQN")

    # 3. Merging
    print("\n[Step 3/4] Performing controlled 1:1 left-join merging on SEQN...")
    merged_df, join_stats = merge_nhanes_components(
        components["demo"],
        components["biopro"],
        components["alb_cr"],
    )
    print(f"  - Demographic cohort: {join_stats['demographic_cohort_count']} participants")
    print(f"  - Matched BIOPRO: {join_stats['biopro_matched_count']} (unmatched: {join_stats['biopro_unmatched_in_demo']})")
    print(f"  - Matched ALB_CR: {join_stats['alb_cr_matched_count']} (unmatched: {join_stats['alb_cr_unmatched_in_demo']})")
    print(f"  - Complete triplets (all 3): {join_stats['complete_cases_all_three_components']}")
    print(f"  - Merged shape: {merged_df.shape}")

    merged_csv_path = processed_dir / "nhanes_2017_2018_merged.csv"
    merged_df.to_csv(merged_csv_path, index=False)
    print(f"  - Merged dataset saved to: {merged_csv_path}")

    # 4. Feature Standardization & Quality Report
    print("\n[Step 4/4] Standardizing clinical features and generating quality audit...")
    features_df = extract_harmonized_ckd_features(merged_df)
    features_csv_path = processed_dir / "nhanes_2017_2018_ckd_features.csv"
    features_df.to_csv(features_csv_path, index=False)
    print(f"  - Harmonized features saved to: {features_csv_path}")

    # Feature mapping metadata
    mapping_path = metadata_dir / "feature_mapping.json"
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(STANDARDIZED_FEATURE_MAPPING, f, indent=2)
    print(f"  - Feature mapping written to: {mapping_path}")

    # Data quality report
    quality_report = generate_nhanes_data_quality_report(merged_df, raw_dfs=components)
    quality_report["merge_statistics"] = join_stats
    report_path = metadata_dir / "data_quality_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2)
    print(f"  - Data quality report written to: {report_path}")

    print("\n" + "=" * 70)
    print("NHANES 2017-2018 Ingestion, Merge, and Harmonization Completed Successfully!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
