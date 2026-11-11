"""Medical evaluation report generators supporting PDF, JSON, CSV, and text export."""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd

from src.clinical.assessment_contracts import UnifiedAssessmentResponse
from src.ui.components.visualizations import render_kdigo_matrix, render_longitudinal_timeline


def sanitize_csv_cell(val: Any) -> Any:
    """Neutralize spreadsheet formula injection characters (OWASP ASVS V5.1.4 / CWE-1236)."""
    if isinstance(val, str) and val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + val
    return val


def generate_text_report(response: UnifiedAssessmentResponse, patient_input: Optional[Dict[str, Any]] = None) -> str:
    """Generate structured medical assessment text report."""
    pt_id = response.patient_id
    ts = response.assessment_timestamp
    e1 = response.engine1_result
    e2 = response.engine2_result
    e3 = response.engine3_result
    prov_source = response.provenance.get('source', 'MANUAL_ENTRY')
    is_synth = prov_source == "SYNTHETIC_DEMONSTRATION" or response.provenance.get('is_synthetic', False)

    synthetic_banner = ""
    if is_synth:
        synthetic_banner = """
================================================================================
⚠️ SYNTHETIC DEMONSTRATION RECORD WARNING:
THIS ASSESSMENT WAS EXECUTED USING AN ILLUSTRATIVE SYNTHETIC PRESET FOR
SOFTWARE VERIFICATION PURPOSES ONLY. IT DOES NOT REPRESENT A GENUINE CLINICAL
PATIENT AND MUST NOT BE USED FOR PATIENT CARE, PRESCRIPTIONS, OR MEDICAL ADVICE.
================================================================================
"""

    report = f"""================================================================================
NEFROAI-X CLINICAL DECISION SUPPORT SYSTEM (CDSS)
MULTIMODAL KIDNEY DISEASE ASSESSMENT REPORT
================================================================================
Assessment ID:        {response.assessment_id}
Patient ID:           {pt_id}
Timestamp (UTC):      {ts}
Orchestrator Version: {response.orchestrator_version}
Provenance Source:    {prov_source}
{synthetic_banner}
MANDATORY CLINICAL DISCLAIMER:
{response.disclaimer}
================================================================================

1. ENGINE 1: SCREENING & BINARY CLASSIFICATION
--------------------------------------------------------------------------------
- Status:                 {e1.status if e1 else 'NOT_REQUESTED'}
- Diagnostic Class:       {e1.diagnosis if e1 else 'N/A'}
- Risk Probability:       {f"{e1.risk_probability*100:.2f}%" if e1 and e1.risk_probability is not None else 'N/A'}
- Clinical Triage Tier:   {e1.risk_category if e1 else 'N/A'}
- Model Confidence:       {f"{e1.confidence_score*100:.1f}%" if e1 and e1.confidence_score is not None else 'N/A'}
- Consensus Completeness: {f"{e1.data_completeness_ratio*100:.1f}%" if e1 else 'N/A'}
"""
    if e1 and e1.clinical_reliability_index is not None:
        report += (
            f"- Clinical Reliability:   CRI={e1.clinical_reliability_index:.2f} | "
            f"Conformal Set={e1.conformal_set} | "
            f"Gate={e1.conformal_gate_decision} ({e1.conformal_gate_status})\n"
        )
    if e1 and e1.mondrian_conformal_set is not None:
        report += f"- Mondrian Set (95%):     {e1.mondrian_conformal_set} (Quantiles={e1.mondrian_quantiles})\n"
    if e1 and e1.stacking_probability is not None:
        report += (
            f"- 4-Family Stacking Risk: {e1.stacking_probability * 100:.2f}% | "
            f"Spread={f'{e1.ensemble_disagreement_spread * 100:.1f}%' if e1.ensemble_disagreement_spread is not None else 'N/A'} | "
            f"Divergent={e1.has_architecture_disagreement}\n"
        )
    if e1 and e1.coherence_audit is not None:
        coh = e1.coherence_audit
        report += (
            f"- Analyte Coherence:      Coherent={coh.get('is_coherent')} | "
            f"Score={coh.get('coherence_score', 1.0):.2f} | Findings={len(coh.get('findings', []))}\n"
        )
    if e1 and e1.missing_features:
        report += f"- Missing Features:       {e1.missing_features}\n"
    if e1 and e1.abstention_reason:
        report += f"- Abstention Rationale:   {e1.abstention_reason}\n"
    if e1 and e1.live_shap_attributions:
        top_shaps = e1.live_shap_attributions.get("top_drivers", [])[:5]
        if top_shaps:
            driver_str = ", ".join(f"{d['feature']} ({d['shap_value']:+.3f})" for d in top_shaps)
            report += f"- Top TreeSHAP Drivers:   {driver_str}\n"

    report += f"""
2. ENGINE 2: KDIGO CGA SEVERITY STAGING (2024 GUIDELINES)
--------------------------------------------------------------------------------
- Status:                 {e2.status if e2 else 'NOT_REQUESTED'}
- Filtration (eGFR):      {f"{e2.egfr:.1f} mL/min/1.73m² ({e2.gfr_category})" if e2 and e2.egfr is not None else 'N/A'}
- Albuminuria (uACR):     {f"{e2.uacr:.1f} mg/g ({e2.albuminuria_category})" if e2 and e2.uacr is not None else 'N/A'}
- CGA Staging String:     {e2.cga_string if e2 else 'N/A'}
- Composite Risk Level:   {e2.composite_risk_level if e2 else 'N/A'}
- Risk Tier:              {e2.risk_tier if e2 else 'N/A'}
- Chronicity Confirmed:   {e2.chronicity_confirmed if e2 else False} (Single-Timepoint Examination)
- Same-Day Measurement:   {e2.same_day_measurement if e2 else 'N/A'}

3. ENGINE 3: LONGITUDINAL PROGRESSION & KFRE RISK
--------------------------------------------------------------------------------
- Status:                 {e3.status if e3 else 'NOT_REQUESTED'}
- Historical OLS Slope:   {f"{e3.historical_egfr_slope:+.2f} mL/min/1.73m²/yr ({e3.slope_status})" if e3 and e3.historical_egfr_slope is not None else 'Insufficient Visits'}
- LMM BLUP Random Slope:  {f"{e3.lmm_annual_slope:+.2f} mL/min/1.73m²/yr" if e3 and e3.lmm_annual_slope is not None else 'Insufficient Visits'}
- KFRE 2-Year Risk:       {f"{e3.kfre_2year_risk*100:.1f}%" if e3 and e3.kfre_2year_risk is not None else 'Withheld / Out of Scope'}
- KFRE 5-Year Risk:       {f"{e3.kfre_5year_risk*100:.1f}%" if e3 and e3.kfre_5year_risk is not None else 'Withheld / Out of Scope'}
- KFRE Calibration:       {e3.kfre_calibration_profile if e3 else 'N/A'}
- Survival Model Status:  {e3.survival_status if e3 else 'DEFERRED'} (Requires Approved CRIC Cohort DUA)
"""
    if e3 and e3.chronicity_aki_assessment:
        aki = e3.chronicity_aki_assessment
        report += f"- Chronicity / AKI Guard: {aki.get('status')} — {aki.get('summary')}\n"
    if e3 and e3.trajectory_backtest and e3.trajectory_backtest.get("eligible"):
        bt = e3.trajectory_backtest
        report += (
            f"- Walk-Forward Backtest:  MAE={bt.get('mae')} | RMSE={bt.get('rmse')} | R2={bt.get('r2')}\n"
        )

    report += """
4. CROSS-ENGINE CLINICAL DISCREPANCIES & SAFETY ALERTS
--------------------------------------------------------------------------------
"""
    if response.clinical_discrepancies:
        for d in response.clinical_discrepancies:
            report += f"[{d.get('severity', 'WARNING')}] {d.get('discrepancy_id')}: {d.get('title')}\n"
            report += f"  Finding: {d.get('description')}\n"
            report += f"  Action:  {d.get('clinical_action')}\n\n"
    else:
        report += "No cross-engine discordance detected across evaluated models.\n"

    arb_tier = (response.overall_completeness or {}).get("arbitration_tier", "ROUTINE_MONITORING")
    arb_detail = (response.overall_completeness or {}).get("arbitration_detail") or {}
    att_sha = (response.provenance or {}).get("attestation_sha256", "NOT_COMPUTED")

    report += f"""
5. SAFETY-MAX ARBITRATION & PROVENANCE ATTESTATION
--------------------------------------------------------------------------------
- Arbitration Priority:   {arb_tier}
- Recommended Action:     {arb_detail.get('recommended_action', 'Proceed with standard clinical correlation.')}
- Attestation SHA-256:    {att_sha}
"""

    report += """
================================================================================
PHYSICIAN REVIEW & SIGN-OFF
--------------------------------------------------------------------------------
Attending Clinician: ___________________________    Date: ______________________
Clinical Action Taken: [ ] Routine Review  [ ] Repeat Labs (3mo)  [ ] Nephrology Referral
================================================================================
"""
    return report


def generate_json_export(response: UnifiedAssessmentResponse) -> str:
    """Export complete unified assessment as formatted JSON."""
    return response.to_json(indent=2)


def generate_csv_export(response: UnifiedAssessmentResponse, patient_input: Optional[Dict[str, Any]] = None) -> str:
    """Export flattened tabular summary of patient inputs and engine results as CSV.

    Sanitizes formula injection characters (=, +, -, @, \\t, \\r) per OWASP ASVS V5.1.4.
    """
    is_synth = response.provenance.get("source") == "SYNTHETIC_DEMONSTRATION" or response.provenance.get("is_synthetic", False)
    flat = {
        "assessment_id": response.assessment_id,
        "patient_id": response.patient_id,
        "timestamp": response.assessment_timestamp,
        "provenance": response.provenance.get("source", "MANUAL_ENTRY"),
        "is_synthetic_demonstration": is_synth,
        # Engine 1
        "e1_status": response.engine1_result.status if response.engine1_result else None,
        "e1_diagnosis": response.engine1_result.diagnosis if response.engine1_result else None,
        "e1_risk_probability": response.engine1_result.risk_probability if response.engine1_result else None,
        "e1_risk_category": response.engine1_result.risk_category if response.engine1_result else None,
        "e1_cri": response.engine1_result.clinical_reliability_index if response.engine1_result else None,
        "e1_conformal_set": str(response.engine1_result.conformal_set) if response.engine1_result and response.engine1_result.conformal_set is not None else None,
        "e1_conformal_gate": response.engine1_result.conformal_gate_decision if response.engine1_result else None,
        "e1_mondrian_set": str(response.engine1_result.mondrian_conformal_set) if response.engine1_result and response.engine1_result.mondrian_conformal_set is not None else None,
        "e1_stacking_probability": response.engine1_result.stacking_probability if response.engine1_result else None,
        "e1_ensemble_spread": response.engine1_result.ensemble_disagreement_spread if response.engine1_result else None,
        "e1_coherence_score": (response.engine1_result.coherence_audit or {}).get("coherence_score") if response.engine1_result else None,
        # Engine 2
        "e2_status": response.engine2_result.status if response.engine2_result else None,
        "e2_egfr": response.engine2_result.egfr if response.engine2_result else None,
        "e2_gfr_category": response.engine2_result.gfr_category if response.engine2_result else None,
        "e2_uacr": response.engine2_result.uacr if response.engine2_result else None,
        "e2_uacr_category": response.engine2_result.albuminuria_category if response.engine2_result else None,
        "e2_kdigo_composite_risk": response.engine2_result.composite_risk_level if response.engine2_result else None,
        # Engine 3
        "e3_status": response.engine3_result.status if response.engine3_result else None,
        "e3_egfr_slope": response.engine3_result.historical_egfr_slope if response.engine3_result else None,
        "e3_lmm_slope": response.engine3_result.lmm_annual_slope if response.engine3_result else None,
        "e3_kfre_2yr": response.engine3_result.kfre_2year_risk if response.engine3_result else None,
        "e3_kfre_5yr": response.engine3_result.kfre_5year_risk if response.engine3_result else None,
        "e3_chronicity_aki_status": (response.engine3_result.chronicity_aki_assessment or {}).get("status") if response.engine3_result else None,
        "discrepancies_count": len(response.clinical_discrepancies),
        "arbitration_tier": (response.overall_completeness or {}).get("arbitration_tier"),
        "attestation_sha256": (response.provenance or {}).get("attestation_sha256"),
    }
    sanitized_flat = {k: sanitize_csv_cell(v) for k, v in flat.items()}
    df = pd.DataFrame([sanitized_flat])
    return df.to_csv(index=False)


def generate_pdf_report(
    response: UnifiedAssessmentResponse,
    observations: Optional[list] = None,
) -> bytes:
    """Generate comprehensive multi-page medical evaluation PDF report."""
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # Page 1: Overview, Engine 1, Engine 2, KDIGO Matrix Chart
        fig1 = plt.figure(figsize=(8.5, 11), dpi=100)
        ax1 = fig1.add_subplot(111)
        ax1.axis("off")

        # Header
        ax1.text(0.05, 0.96, "NEFROAI-X CLINICAL DECISION SUPPORT SYSTEM", fontsize=15, fontweight="bold", color="#0f4c81")
        ax1.text(0.05, 0.935, "Multimodal Renal Disease Screening, Staging & Progression Assessment", fontsize=10, color="#475569")
        ax1.axhline(0.925, color="#0f4c81", linewidth=1.5)

        # Meta & Disclaimer
        is_synth = response.provenance.get("source") == "SYNTHETIC_DEMONSTRATION" or response.provenance.get("is_synthetic", False)
        synth_tag = "  |  [DEMONSTRATION RECORD — NOT A REAL PATIENT]" if is_synth else ""
        meta_txt = (
            f"Assessment ID: {response.assessment_id}  |  Patient ID: {response.patient_id}{synth_tag}  |  "
            f"Date: {response.assessment_timestamp[:10]}\n"
            f"RESEARCH SOFTWARE ONLY — NOT CLINICALLY VALIDATED FOR INDEPENDENT DIAGNOSIS"
        )
        ax1.text(0.05, 0.89, meta_txt, fontsize=8.5, color="#b91c1c" if is_synth else "#92400e", fontweight="bold")

        # Engine 1 Box
        e1 = response.engine1_result
        e1_body = "Engine 1 was not executed or not requested."
        if e1:
            if e1.risk_probability is not None:
                cri_line = (
                    f"\nCD-CIRPVM Gate: {e1.conformal_gate_decision} | CRI: {e1.clinical_reliability_index:.2f} | "
                    f"Conformal Set: {e1.conformal_set} (q̂={e1.conformal_quantile:.3f})"
                    if e1.clinical_reliability_index is not None and e1.conformal_quantile is not None
                    else ""
                )
                extra_e1 = ""
                if e1.stacking_probability is not None or e1.mondrian_conformal_set is not None:
                    stk_p = f"{e1.stacking_probability*100:.1f}%" if e1.stacking_probability is not None else "N/A"
                    coh_sc = (e1.coherence_audit or {}).get("coherence_score", 1.0)
                    extra_e1 = f"\nStacking Risk: {stk_p} | Mondrian Set: {e1.mondrian_conformal_set} | Coherence: {coh_sc:.2f}"
                e1_body = (
                    f"Diagnostic Class: {e1.diagnosis}\n"
                    f"Calibrated Disease Risk: {e1.risk_probability*100:.1f}%  |  "
                    f"Triage Tier: {e1.risk_category}  |  Confidence: {e1.confidence_score*100:.1f}%\n"
                    f"Panel Completeness: {e1.data_completeness_ratio*100:.1f}% (Top-10 Features)"
                    f"{cri_line}{extra_e1}"
                )
            else:
                e1_body = f"Screening Withheld: {e1.abstention_reason}"

        ax1.text(0.05, 0.84, "1. ENGINE 1: SCREENING & BINARY CLASSIFICATION", fontsize=11, fontweight="bold", color="#0f4c81")
        ax1.text(0.05, 0.77, e1_body, fontsize=9, color="#1e293b", linespacing=1.4)

        # Engine 2 Box
        e2 = response.engine2_result
        e2_body = "Engine 2 was not executed or not requested."
        g_cat = None
        a_cat = None
        if e2:
            g_cat = e2.gfr_category
            a_cat = e2.albuminuria_category
            e2_body = (
                f"Filtration (eGFR): {e2.egfr:.1f} mL/min/1.73m² ({e2.gfr_category}: {e2.gfr_description})\n"
                f"Albuminuria (uACR): {e2.uacr:.1f} mg/g ({e2.albuminuria_category}: {e2.albuminuria_description})\n"
                f"KDIGO CGA Staging: {e2.cga_string}  |  Composite Risk: {e2.composite_risk_level} ({e2.risk_tier})\n"
                f"Limitation: Cross-sectional examination (requires >=3 months persistence to confirm CKD)"
            ) if e2.egfr is not None else "Incomplete Staging Panel"

        ax1.text(0.05, 0.71, "2. ENGINE 2: KDIGO CGA SEVERITY STAGING (2024)", fontsize=11, fontweight="bold", color="#0f4c81")
        ax1.text(0.05, 0.61, e2_body, fontsize=9, color="#1e293b", linespacing=1.4)

        # Draw KDIGO matrix thumbnail
        k_fig = render_kdigo_matrix(g_cat, a_cat, figsize=(5.5, 3.2))
        k_buf = io.BytesIO()
        k_fig.savefig(k_buf, format="png", bbox_inches="tight", dpi=100)
        plt.close(k_fig)
        k_buf.seek(0)
        k_img = plt.imread(k_buf)
        ax1.imshow(k_img, extent=[0.12, 0.88, 0.20, 0.58])

        # Discrepancy Alert Box on Page 1
        disc_text = "No clinical discrepancies detected."
        if response.clinical_discrepancies:
            d0 = response.clinical_discrepancies[0]
            disc_text = f"[{d0.get('severity')}] {d0.get('discrepancy_id')}: {d0.get('title')}\n{d0.get('description')}\nAction: {d0.get('clinical_action')}"

        ax1.text(0.05, 0.15, "3. CROSS-ENGINE SAFETY & DISCORDANCE AUDIT", fontsize=10, fontweight="bold", color="#0f4c81")
        ax1.text(0.05, 0.04, disc_text, fontsize=8, color="#b91c1c" if response.clinical_discrepancies else "#065f46", linespacing=1.3)

        pdf.savefig(fig1)
        plt.close(fig1)

        # Page 2: Engine 3, Timeline Chart, Signatures
        fig2 = plt.figure(figsize=(8.5, 11), dpi=100)
        ax2 = fig2.add_subplot(111)
        ax2.axis("off")

        ax2.text(0.05, 0.96, "NEFROAI-X CLINICAL ASSESSMENT REPORT (PAGE 2)", fontsize=13, fontweight="bold", color="#0f4c81")
        ax2.axhline(0.94, color="#0f4c81", linewidth=1.5)

        # Engine 3 details
        e3 = response.engine3_result
        e3_body = "Engine 3 was not executed."
        slope = None
        lmm_slope = None
        if e3:
            slope = e3.historical_egfr_slope
            lmm_slope = e3.lmm_annual_slope
            kfre_txt = f"2-Yr: {e3.kfre_2year_risk*100:.1f}%, 5-Yr: {e3.kfre_5year_risk*100:.1f}% ({e3.kfre_calibration_profile})" if e3.kfre_2year_risk is not None else "Withheld / Out of Target Scope"
            aki_stat = (e3.chronicity_aki_assessment or {}).get("status", "N/A")
            e3_body = (
                f"Historical eGFR Slope (OLS): {f'{slope:+.2f} mL/min/1.73m²/yr' if slope else 'Insufficient visits (<2)'}\n"
                f"LMM BLUP Random Slope:        {f'{lmm_slope:+.2f} mL/min/1.73m²/yr' if lmm_slope else 'Insufficient visits (<3)'}\n"
                f"Tangri 4-Variable KFRE Risk:  {kfre_txt}\n"
                f"Chronicity / AKI Velocity:    {aki_stat}\n"
                f"Survival Model Inference:     DEFERRED (Pending Approved NIDDK CRIC Longitudinal Cohort DUA)"
            )

        ax2.text(0.05, 0.89, "4. ENGINE 3: LONGITUDINAL PROGRESSION & KFRE RISK", fontsize=11, fontweight="bold", color="#0f4c81")
        ax2.text(0.05, 0.77, e3_body, fontsize=9, color="#1e293b", linespacing=1.4)

        # Render longitudinal timeline chart on page 2
        t_fig = render_longitudinal_timeline(observations or [], slope=slope, lmm_slope=lmm_slope, figsize=(6.0, 3.5))
        t_buf = io.BytesIO()
        t_fig.savefig(t_buf, format="png", bbox_inches="tight", dpi=100)
        plt.close(t_fig)
        t_buf.seek(0)
        t_img = plt.imread(t_buf)
        ax2.imshow(t_img, extent=[0.10, 0.90, 0.28, 0.72])

        # Clinical Sign-off block
        arb_tier_pdf = (response.overall_completeness or {}).get("arbitration_tier", "ROUTINE_MONITORING")
        att_sha_pdf = (response.provenance or {}).get("attestation_sha256", "N/A")
        sign_txt = (
            "================================================================================\n"
            f"SAFETY-MAX ARBITRATION: {arb_tier_pdf}\n"
            f"PROVENANCE SHA-256:     {att_sha_pdf}\n"
            "CLINICAL REVIEW & ATTESTATION:\n"
            "Attending Physician: ___________________________    Date: _____________________\n"
            "Signature:          ___________________________    NPI:  _____________________\n"
            "Clinical Judgment:  [ ] Approved for Screening   [ ] Formal Nephrology Referral\n"
            "================================================================================"
        )
        ax2.text(0.05, 0.06, sign_txt, fontsize=8.0, family="monospace", color="#334155")

        pdf.savefig(fig2)
        plt.close(fig2)

    buf.seek(0)
    return buf.getvalue()
