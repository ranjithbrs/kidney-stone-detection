"""Cross-Analyte Physiological & Stoichiometric Coherence Verifier.

Detects multi-biomarker physiological contradictions indicative of specimen
swaps, hemolysis, clerical transcription errors, or cross-engine laboratory
discordance before model predictions are presented to clinicians.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CoherenceFinding:
    """Single cross-analyte physiological contradiction finding."""

    check_id: str
    title: str
    severity: str  # "WARNING" | "CRITICAL"
    involved_analytes: List[str]
    observed_detail: str
    expected_invariant: str
    cri_penalty: float
    clinical_action: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoherenceAuditResult:
    """Aggregated pre-inference and cross-engine coherence audit."""

    is_coherent: bool
    coherence_score: float
    total_cri_penalty: float
    checks_evaluated: int
    findings: List[Dict[str, Any]] = field(default_factory=list)
    specimen_verification_recommended: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_coherent": self.is_coherent,
            "coherence_score": self.coherence_score,
            "total_cri_penalty": self.total_cri_penalty,
            "checks_evaluated": self.checks_evaluated,
            "findings": list(self.findings),
            "specimen_verification_recommended": self.specimen_verification_recommended,
        }


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(str(val).strip().replace("\t", ""))
        return f if f == f else None
    except (ValueError, TypeError):
        return None


def verify_cross_analyte_coherence(
    biomarkers: Dict[str, Any],
    uacr_mg_g: Optional[float] = None,
) -> CoherenceAuditResult:
    """Verify multi-biomarker physiological invariants on canonical clinical inputs.

    Checks evaluated when required analyte pairs are present:
    1. Hematology Rule-of-3: PCV (%) should track ~3 * Hemoglobin (g/dL).
    2. Erythrocyte MCV Proxy: (10 * PCV) / RBC should lie in plausible 50-135 fL.
    3. Urea-to-Creatinine Ratio: extreme mismatch flags possible BUN/Urea confusion.
    4. Dipstick Albumin vs. Quantitative uACR: detects conflicting proteinuria severity.
    """
    findings: List[CoherenceFinding] = []
    checks_evaluated = 0

    hemo = _to_float(biomarkers.get("hemo"))
    pcv = _to_float(biomarkers.get("pcv"))
    rc = _to_float(biomarkers.get("rc"))
    sc = _to_float(biomarkers.get("sc"))
    bu = _to_float(biomarkers.get("bu"))
    al = _to_float(biomarkers.get("al"))

    # 1. Hematology Rule-of-3: PCV ≈ 3 * Hemoglobin (tolerance ±12 percentage points)
    if hemo is not None and pcv is not None and hemo > 0 and pcv > 0:
        checks_evaluated += 1
        expected_pcv = 3.0 * hemo
        diff = abs(pcv - expected_pcv)
        if diff > 12.0:
            findings.append(CoherenceFinding(
                check_id="COH-01-HEMO-PCV-MISMATCH",
                title="Hemoglobin–Hematocrit (Rule-of-3) Physiological Contradiction",
                severity="CRITICAL" if diff > 18.0 else "WARNING",
                involved_analytes=["hemo", "pcv"],
                observed_detail=f"Hemoglobin={hemo:.1f} g/dL vs. PCV={pcv:.1f}% (|Δ|={diff:.1f}%)",
                expected_invariant=f"Expected PCV ≈ 3 × hemo ({expected_pcv:.1f}% ± 12%)",
                cri_penalty=0.15 if diff > 18.0 else 0.08,
                clinical_action="Verify CBC transcription or check for severe hemolysis / specimen dilution; repeat draw if unexpected.",
            ))

    # 2. Erythrocyte MCV Proxy: MCV = (10 * PCV) / RBC (viable human RBC range ~50–135 fL)
    if pcv is not None and rc is not None and pcv > 0 and rc > 0:
        checks_evaluated += 1
        mcv_proxy = (10.0 * pcv) / rc
        if mcv_proxy < 48.0 or mcv_proxy > 140.0:
            findings.append(CoherenceFinding(
                check_id="COH-02-RBC-PCV-MCV-IMPLAUSIBLE",
                title="Erythrocyte Index (MCV Proxy) Physiological Impossibility",
                severity="WARNING",
                involved_analytes=["pcv", "rc"],
                observed_detail=f"PCV={pcv:.1f}%, RBC={rc:.2f} M/mcL -> implied MCV={mcv_proxy:.1f} fL",
                expected_invariant="Physiological MCV range: 48.0 – 140.0 fL",
                cri_penalty=0.08,
                clinical_action="Verify red cell count unit scale (M/mcL) and hematocrit percentage.",
            ))

    # 3. Blood Urea vs. Serum Creatinine Stoichiometric Ratio Check
    if bu is not None and sc is not None and sc > 0 and bu > 0:
        checks_evaluated += 1
        ratio = bu / sc
        # Extremely low Urea/SC ratio (< 4) with high SC or extremely high ratio (> 120) with normal SC
        if (sc >= 2.0 and ratio < 4.0) or (sc <= 1.2 and ratio > 110.0):
            findings.append(CoherenceFinding(
                check_id="COH-03-UREA-CREATININE-RATIO",
                title="Blood Urea / Creatinine Ratio Anomaly (Potential BUN vs. Urea Mismatch)",
                severity="WARNING",
                involved_analytes=["bu", "sc"],
                observed_detail=f"bu={bu:.1f} mg/dL, sc={sc:.2f} mg/dL (bu/sc={ratio:.1f})",
                expected_invariant="Typical Whole Urea/SC ratio lies within 8–100 across clinical presentations",
                cri_penalty=0.06,
                clinical_action="Confirm whether reported urea represents BUN (convert ×2.143) or Whole Blood Urea.",
            ))

    # 4. Cross-Engine Urine Dipstick Albumin vs. Quantitative uACR Concordance
    if al is not None and uacr_mg_g is not None:
        checks_evaluated += 1
        if al <= 0.0 and uacr_mg_g >= 300.0:
            findings.append(CoherenceFinding(
                check_id="COH-04-DIPSTICK-UACR-DISCORDANCE",
                title="Negative Urine Dipstick vs. Severe Quantitative Albuminuria",
                severity="CRITICAL",
                involved_analytes=["al", "uacr"],
                observed_detail=f"Dipstick al={int(al)} while quantitative uACR={uacr_mg_g:.1f} mg/g (A3)",
                expected_invariant="uACR >= 300 mg/g typically registers >= 1+ on dipstick albumin",
                cri_penalty=0.10,
                clinical_action="Prioritize quantitative uACR (A3) over dipstick negative; verify concurrent specimen dates.",
            ))
        elif al >= 3.0 and uacr_mg_g < 15.0:
            findings.append(CoherenceFinding(
                check_id="COH-04-DIPSTICK-UACR-DISCORDANCE",
                title="High Urine Dipstick vs. Normal Quantitative uACR",
                severity="WARNING",
                involved_analytes=["al", "uacr"],
                observed_detail=f"Dipstick al={int(al)} while quantitative uACR={uacr_mg_g:.1f} mg/g (A1)",
                expected_invariant="Dipstick >= 3+ conflicts with normoalbuminuria (<15 mg/g)",
                cri_penalty=0.08,
                clinical_action="Verify specimen timing or non-albumin proteinuria / false-positive alkaline dipstick.",
            ))

    total_penalty = round(min(0.60, sum(f.cri_penalty for f in findings)), 2)
    coherence_score = round(max(0.0, 1.0 - total_penalty), 2)
    specimen_redraw = any(f.severity == "CRITICAL" for f in findings) or total_penalty >= 0.15

    return CoherenceAuditResult(
        is_coherent=len(findings) == 0,
        coherence_score=coherence_score,
        total_cri_penalty=total_penalty,
        checks_evaluated=checks_evaluated,
        findings=[f.to_dict() for f in findings],
        specimen_verification_recommended=specimen_redraw,
    )

