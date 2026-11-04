#!/usr/bin/env python3
"""
Generate high-fidelity SVG architecture diagrams for NEFROAI-X.
Outputs to docs/images/:
  1. nefroai_x_complete_architecture.svg
  2. engine1_architecture.svg
  3. engine2_architecture.svg
  4. engine3_architecture.svg
  5. unified_assessment_workflow.svg
  6. clinical_reliability_abstention_workflow.svg
  7. docker_deployment_architecture.svg
"""

import os

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "images")
os.makedirs(OUT_DIR, exist_ok=True)

# Helper to write SVG
def write_svg(filename, content):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"Generated: {path}")

# 1. Complete Architecture
svg1 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 700" width="100%" height="100%">
  <defs>
    <linearGradient id="gradHeader" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0f4c81"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity="0.15"/>
    </filter>
  </defs>

  <rect width="1100" height="700" fill="#f8fafc"/>

  <!-- Title Banner -->
  <rect x="30" y="25" width="1040" height="70" rx="8" fill="url(#gradHeader)" filter="url(#shadow)"/>
  <text x="50" y="60" fill="#ffffff" font-family="system-ui, sans-serif" font-size="22" font-weight="bold">NEFROAI-X: Multimodal Kidney Disease Clinical Decision Support System</text>
  <text x="50" y="82" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="13">High-Level System Architecture &amp; Three-Engine Integration Layer</text>

  <!-- Input Layer -->
  <rect x="30" y="115" width="220" height="420" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="30" y="115" width="220" height="40" rx="8" fill="#e2e8f0"/>
  <text x="45" y="140" fill="#334155" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">Clinical Inputs &amp; Data</text>

  <g transform="translate(45, 175)" font-family="system-ui, sans-serif" font-size="12" fill="#1e293b">
    <rect width="190" height="45" rx="6" fill="#f1f5f9" stroke="#94a3b8"/>
    <text x="10" y="20" font-weight="bold">Patient Demographics</text>
    <text x="10" y="36" fill="#64748b" font-size="11">Age, Sex, Clinical Preset</text>

    <g transform="translate(0, 55)">
      <rect width="190" height="45" rx="6" fill="#f1f5f9" stroke="#94a3b8"/>
      <text x="10" y="20" font-weight="bold">10 Consensus Biomarkers</text>
      <text x="10" y="36" fill="#64748b" font-size="11">SC, Hemo, SG, PCV, AL...</text>
    </g>

    <g transform="translate(0, 110)">
      <rect width="190" height="45" rx="6" fill="#f1f5f9" stroke="#94a3b8"/>
      <text x="10" y="20" font-weight="bold">Renal Laboratory Panel</text>
      <text x="10" y="36" fill="#64748b" font-size="11">eGFR, UACR, Urea, Glucose</text>
    </g>

    <g transform="translate(0, 165)">
      <rect width="190" height="45" rx="6" fill="#f1f5f9" stroke="#94a3b8"/>
      <text x="10" y="20" font-weight="bold">Longitudinal Trajectory</text>
      <text x="10" y="36" fill="#64748b" font-size="11">Repeated SC/eGFR records</text>
    </g>

    <g transform="translate(0, 220)">
      <rect width="190" height="45" rx="6" fill="#fef2f2" stroke="#f87171"/>
      <text x="10" y="20" font-weight="bold" fill="#b91c1c">CD-CIRPVM Quality Gate</text>
      <text x="10" y="36" fill="#dc2626" font-size="11">CRI score &amp; bounds check</text>
    </g>
  </g>

  <!-- Orchestration & Engines -->
  <rect x="280" y="115" width="530" height="420" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="280" y="115" width="530" height="40" rx="8" fill="#e2e8f0"/>
  <text x="295" y="140" fill="#334155" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">Unified Assessment Orchestrator (Backend Engine Layer)</text>

  <!-- Engine 1 Box -->
  <g transform="translate(300, 175)">
    <rect width="490" height="70" rx="6" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
    <text x="15" y="24" fill="#1e40af" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">Engine 1: Binary CKD Screening &amp; Risk Classification</text>
    <text x="15" y="42" fill="#3b82f6" font-family="system-ui, sans-serif" font-size="11">Tuned Random Forest (50 trees) - 10 Consensus Biomarkers - Calibration &amp; Triaging</text>
    <text x="15" y="58" fill="#64748b" font-family="system-ui, sans-serif" font-size="11">Explainability: SHAP TreeExplainer &amp; LIME Tabular Local Decision Rules</text>
  </g>

  <!-- Engine 2 Box -->
  <g transform="translate(300, 260)">
    <rect width="490" height="70" rx="6" fill="#f0fdf4" stroke="#22c55e" stroke-width="1.5"/>
    <text x="15" y="24" fill="#166534" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">Engine 2: KDIGO 2024 CGA Severity Staging</text>
    <text x="15" y="42" fill="#15803d" font-family="system-ui, sans-serif" font-size="11">Race-Free CKD-EPI 2021 eGFR - Staging G1–G5 - Albuminuria Staging A1–A3</text>
    <text x="15" y="58" fill="#64748b" font-family="system-ui, sans-serif" font-size="11">KDIGO Composite Risk Heatmap - Chronicity &amp; Discrepancy Warnings</text>
  </g>

  <!-- Engine 3 Box -->
  <g transform="translate(300, 345)">
    <rect width="490" height="85" rx="6" fill="#fdf4ff" stroke="#c084fc" stroke-width="1.5"/>
    <text x="15" y="24" fill="#6b21a8" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">Engine 3: Longitudinal Kidney Progression &amp; Risk Engine</text>
    <text x="15" y="42" fill="#9333ea" font-family="system-ui, sans-serif" font-size="11">Tangri 4-Variable KFRE Reference Calculator (2-year &amp; 5-year failure risk)</text>
    <text x="15" y="58" fill="#7e22ce" font-family="system-ui, sans-serif" font-size="11">eGFR Slope Trajectory: OLS Annualized Rate &amp; Linear Mixed-Effects Model (BLUP)</text>
    <text x="15" y="74" fill="#64748b" font-family="system-ui, sans-serif" font-size="11">Survival Architecture: Cox PH &amp; RSF (Deferred pending approved DUA cohort)</text>
  </g>

  <!-- Discrepancy Synthesis -->
  <g transform="translate(300, 445)">
    <rect width="490" height="65" rx="6" fill="#fffbeb" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="15" y="24" fill="#92400e" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">Clinical Discrepancy Engine (DISC-01 to DISC-08)</text>
    <text x="15" y="42" fill="#b45309" font-family="system-ui, sans-serif" font-size="11">Cross-engine coherence auditing: screening probability vs GFR/ACR staging discordance,</text>
    <text x="15" y="56" fill="#b45309" font-family="system-ui, sans-serif" font-size="11">single-observation chronicity gaps, and KFRE eGFR &gt;= 60 applicability withholding.</text>
  </g>

  <!-- Presentation & Export -->
  <rect x="840" y="115" width="230" height="420" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="840" y="115" width="230" height="40" rx="8" fill="#e2e8f0"/>
  <text x="855" y="140" fill="#334155" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">Clinical UX &amp; Export</text>

  <g transform="translate(855, 175)" font-family="system-ui, sans-serif" font-size="12" fill="#1e293b">
    <rect width="200" height="45" rx="6" fill="#f8fafc" stroke="#94a3b8"/>
    <text x="10" y="20" font-weight="bold">Streamlit Web UI</text>
    <text x="10" y="36" fill="#64748b" font-size="11">Responsive multi-tab navigation</text>

    <g transform="translate(0, 55)">
      <rect width="200" height="45" rx="6" fill="#f8fafc" stroke="#94a3b8"/>
      <text x="10" y="20" font-weight="bold">Interactive Visuals</text>
      <text x="10" y="36" fill="#64748b" font-size="11">KDIGO matrix, trajectory plot</text>
    </g>

    <g transform="translate(0, 110)">
      <rect width="200" height="45" rx="6" fill="#f8fafc" stroke="#94a3b8"/>
      <text x="10" y="20" font-weight="bold">Explainability Suite</text>
      <text x="10" y="36" fill="#64748b" font-size="11">SHAP waterfall &amp; LIME bars</text>
    </g>

    <g transform="translate(0, 165)">
      <rect width="200" height="65" rx="6" fill="#eff6ff" stroke="#3b82f6"/>
      <text x="10" y="20" font-weight="bold" fill="#1e40af">Multi-Format Export</text>
      <text x="10" y="36" fill="#2563eb" font-size="11">- Vector PDF (ReportLab)</text>
      <text x="10" y="52" fill="#2563eb" font-size="11">- Sanitized CSV, JSON, TXT</text>
    </g>

    <g transform="translate(0, 240)">
      <rect width="200" height="45" rx="6" fill="#fef2f2" stroke="#ef4444"/>
      <text x="10" y="20" font-weight="bold" fill="#991b1b">Demonstration Provenance</text>
      <text x="10" y="36" fill="#b91c1c" font-size="11">Synthetic banners embedded</text>
    </g>
  </g>

  <!-- Bottom Disclaimer Banner -->
  <rect x="30" y="555" width="1040" height="110" rx="8" fill="#1e293b" filter="url(#shadow)"/>
  <text x="50" y="582" fill="#fbbf24" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">MANDATORY CLINICAL &amp; REGULATORY DESIGNATION:</text>
  <text x="50" y="605" fill="#f8fafc" font-family="system-ui, sans-serif" font-size="12">INVESTIGATIONAL RESEARCH SOFTWARE - NOT A CERTIFIED MEDICAL DEVICE - LOCAL RESEARCH SOFTWARE ONLY (127.0.0.1 BINDING)</text>
  <text x="50" y="626" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">NEFROAI-X is an algorithmic research platform replicating IEEE Access NefroAI and KDIGO guidelines for risk triaging and medical education.</text>
  <text x="50" y="644" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">It does not establish a definitive medical diagnosis, replace nephrologist consultation, or prescribe therapeutic regimens.</text>
</svg>"""

write_svg("nefroai_x_complete_architecture.svg", svg1)

# 2. Engine 1 Architecture
svg2 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" width="100%" height="100%">
  <rect width="900" height="500" fill="#f8fafc"/>
  <rect x="20" y="20" width="860" height="60" rx="6" fill="#1e3a8a"/>
  <text x="40" y="55" fill="#ffffff" font-family="system-ui, sans-serif" font-size="18" font-weight="bold">Engine 1: Binary CKD Screening &amp; Explainable Classification</text>

  <!-- Flow Steps -->
  <g transform="translate(30, 110)" font-family="system-ui, sans-serif" font-size="12">
    <!-- Step 1 -->
    <rect width="180" height="180" rx="6" fill="#ffffff" stroke="#93c5fd" stroke-width="2"/>
    <rect width="180" height="35" rx="6" fill="#dbeafe"/>
    <text x="15" y="23" font-weight="bold" fill="#1e40af">1. Consensus Inputs</text>
    <text x="15" y="55" fill="#334155">Top-10 Biomarkers:</text>
    <text x="15" y="73" fill="#64748b" font-size="11">- Hemoglobin (hemo)</text>
    <text x="15" y="89" fill="#64748b" font-size="11">- Specific Gravity (sg)</text>
    <text x="15" y="105" fill="#64748b" font-size="11">- Packed Cell Vol (pcv)</text>
    <text x="15" y="121" fill="#64748b" font-size="11">- Red Blood Cells (rc)</text>
    <text x="15" y="137" fill="#64748b" font-size="11">- Albumin (al)</text>
    <text x="15" y="153" fill="#64748b" font-size="11">- SC, BU, BGR, HTN, DM</text>

    <!-- Arrow 1 -->
    <path d="M 190 90 L 220 90" stroke="#3b82f6" stroke-width="3" fill="none" marker-end="url(#arrow)"/>

    <!-- Step 2 -->
    <g transform="translate(230, 0)">
      <rect width="180" height="180" rx="6" fill="#ffffff" stroke="#93c5fd" stroke-width="2"/>
      <rect width="180" height="35" rx="6" fill="#dbeafe"/>
      <text x="15" y="23" font-weight="bold" fill="#1e40af">2. Preprocessing</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">Leak-Free Pipeline:</text>
      <text x="15" y="80" fill="#64748b" font-size="11">- Median imputation</text>
      <text x="15" y="96" fill="#64748b" font-size="11">  (fitted on X_train)</text>
      <text x="15" y="116" fill="#64748b" font-size="11">- Standard scaling</text>
      <text x="15" y="132" fill="#64748b" font-size="11">  (zero train/test leak)</text>
      <text x="15" y="152" fill="#64748b" font-size="11">- Categorical mapping</text>
    </g>

    <!-- Step 3 -->
    <g transform="translate(450, 0)">
      <rect width="180" height="180" rx="6" fill="#ffffff" stroke="#93c5fd" stroke-width="2"/>
      <rect width="180" height="35" rx="6" fill="#dbeafe"/>
      <text x="15" y="23" font-weight="bold" fill="#1e40af">3. Champion Model</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">Random Forest:</text>
      <text x="15" y="80" fill="#64748b" font-size="11">- 50 Estimators</text>
      <text x="15" y="96" fill="#64748b" font-size="11">- Random state 42</text>
      <text x="15" y="116" fill="#64748b" font-size="11">- Stratified 5-Fold</text>
      <text x="15" y="132" fill="#64748b" font-size="11">  hyperparameter tuned</text>
      <text x="15" y="152" fill="#64748b" font-size="11">- 141 KB bundle</text>
    </g>

    <!-- Step 4 -->
    <g transform="translate(670, 0)">
      <rect width="170" height="180" rx="6" fill="#ffffff" stroke="#93c5fd" stroke-width="2"/>
      <rect width="170" height="35" rx="6" fill="#dbeafe"/>
      <text x="15" y="23" font-weight="bold" fill="#1e40af">4. Explainability</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">Dual-Layer XAI:</text>
      <text x="15" y="80" fill="#64748b" font-size="11">- SHAP TreeExplainer</text>
      <text x="15" y="96" fill="#64748b" font-size="11">  (Game-theoretic values)</text>
      <text x="15" y="116" fill="#64748b" font-size="11">- Local waterfall plots</text>
      <text x="15" y="136" fill="#64748b" font-size="11">- LIME surrogate rules</text>
      <text x="15" y="152" fill="#64748b" font-size="11">  (Linear bounds)</text>
    </g>
  </g>

  <!-- Bottom Output Banner -->
  <rect x="30" y="320" width="840" height="140" rx="6" fill="#ffffff" stroke="#cbd5e1"/>
  <text x="50" y="350" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#1e293b">Engine 1 Outputs &amp; Decision Support Stratification:</text>
  <text x="50" y="380" font-family="system-ui, sans-serif" font-size="12" fill="#475569">- Diagnostic Class: 0 (Normal / Healthy Control) vs 1 (Chronic Kidney Disease At Risk)</text>
  <text x="50" y="405" font-family="system-ui, sans-serif" font-size="12" fill="#475569">- Risk Probability: Continuous calibrated probability [0.0 - 1.0] derived from ensemble vote</text>
  <text x="50" y="430" font-family="system-ui, sans-serif" font-size="12" fill="#475569">- Clinical Triage Tiers: Low (&lt;20%), Moderate (20-50%), High (50-80%), Critical (&gt;=80%)</text>
</svg>"""

write_svg("engine1_architecture.svg", svg2)

# 3. Engine 2 Architecture
svg3 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" width="100%" height="100%">
  <rect width="900" height="500" fill="#f8fafc"/>
  <rect x="20" y="20" width="860" height="60" rx="6" fill="#166534"/>
  <text x="40" y="55" fill="#ffffff" font-family="system-ui, sans-serif" font-size="18" font-weight="bold">Engine 2: KDIGO 2024 CGA Severity Staging &amp; Risk Matrix</text>

  <g transform="translate(30, 110)" font-family="system-ui, sans-serif" font-size="12">
    <!-- Component 1 -->
    <rect width="250" height="200" rx="6" fill="#ffffff" stroke="#86efac" stroke-width="2"/>
    <rect width="250" height="35" rx="6" fill="#dcfce7"/>
    <text x="15" y="23" font-weight="bold" fill="#166534">Race-Free CKD-EPI 2021</text>
    <text x="15" y="60" fill="#334155" font-weight="bold">Equation Inputs:</text>
    <text x="15" y="80" fill="#64748b" font-size="11">- Serum Creatinine (mg/dL or umol/L)</text>
    <text x="15" y="98" fill="#64748b" font-size="11">- Age (years) &amp; Biological Sex</text>
    <text x="15" y="125" fill="#334155" font-weight="bold">GFR Categories:</text>
    <text x="15" y="145" fill="#64748b" font-size="11">G1 (&gt;=90), G2 (60-89), G3a (45-59),</text>
    <text x="15" y="163" fill="#64748b" font-size="11">G3b (30-44), G4 (15-29), G5 (&lt;15)</text>
    <text x="15" y="183" fill="#16a34a" font-size="11" font-weight="bold">No race coefficient applied</text>

    <!-- Component 2 -->
    <g transform="translate(290, 0)">
      <rect width="250" height="200" rx="6" fill="#ffffff" stroke="#86efac" stroke-width="2"/>
      <rect width="250" height="35" rx="6" fill="#dcfce7"/>
      <text x="15" y="23" font-weight="bold" fill="#166534">Albuminuria Staging</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">Biomarker Inputs:</text>
      <text x="15" y="80" fill="#64748b" font-size="11">- Urine Albumin-Creatinine Ratio</text>
      <text x="15" y="98" fill="#64748b" font-size="11">  (UACR in mg/g or mg/mmol)</text>
      <text x="15" y="125" fill="#334155" font-weight="bold">Albuminuria Categories:</text>
      <text x="15" y="145" fill="#64748b" font-size="11">A1: Normal/Mild (&lt;30 mg/g)</text>
      <text x="15" y="163" fill="#64748b" font-size="11">A2: Moderately Increased (30-300)</text>
      <text x="15" y="181" fill="#64748b" font-size="11">A3: Severely Increased (&gt;300)</text>
    </g>

    <!-- Component 3 -->
    <g transform="translate(580, 0)">
      <rect width="260" height="200" rx="6" fill="#ffffff" stroke="#86efac" stroke-width="2"/>
      <rect width="260" height="35" rx="6" fill="#dcfce7"/>
      <text x="15" y="23" font-weight="bold" fill="#166534">KDIGO Composite Risk Grid</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">28 Heatmap Risk Cells:</text>
      <text x="15" y="85" fill="#22c55e" font-weight="bold">&#9632; Low Risk (Green): G1A1, G2A1</text>
      <text x="15" y="105" fill="#eab308" font-weight="bold">&#9632; Moderately High (Yellow): G3aA1, G1A2</text>
      <text x="15" y="125" fill="#f97316" font-weight="bold">&#9632; High Risk (Orange): G3bA1, G3aA2</text>
      <text x="15" y="145" fill="#ef4444" font-weight="bold">&#9632; Very High (Red): G4/G5, A3</text>
      <text x="15" y="175" fill="#64748b" font-size="11">Generates combined CGA string (e.g. G3bA2)</text>
    </g>
  </g>

  <!-- Bottom Note -->
  <rect x="30" y="340" width="840" height="120" rx="6" fill="#ffffff" stroke="#cbd5e1"/>
  <text x="50" y="370" font-family="system-ui, sans-serif" font-size="13" font-weight="bold" fill="#b91c1c">Clinical Chronicity Caveat (DISC-03 Safeguard):</text>
  <text x="50" y="395" fill="#475569" font-family="system-ui, sans-serif" font-size="12">Under KDIGO 2024 guidelines, CKD requires documentation of kidney abnormalities persisting for &gt; 3 months.</text>
  <text x="50" y="415" fill="#475569" font-family="system-ui, sans-serif" font-size="12">Single point-of-care lab observations reflect instantaneous filtration status and cannot independently rule out Acute Kidney Injury (AKI).</text>
  <text x="50" y="435" fill="#475569" font-family="system-ui, sans-serif" font-size="12">Engine 2 automatically appends an explicit chronicity verification advisory to all generated reports.</text>
</svg>"""

write_svg("engine2_architecture.svg", svg3)

# 4. Engine 3 Architecture
svg4 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 520" width="100%" height="100%">
  <rect width="900" height="520" fill="#f8fafc"/>
  <rect x="20" y="20" width="860" height="60" rx="6" fill="#6b21a8"/>
  <text x="40" y="55" fill="#ffffff" font-family="system-ui, sans-serif" font-size="18" font-weight="bold">Engine 3: Longitudinal Progression &amp; Survival Risk Architecture</text>

  <g transform="translate(30, 110)" font-family="system-ui, sans-serif" font-size="12">
    <!-- Left: KFRE -->
    <rect width="400" height="220" rx="6" fill="#ffffff" stroke="#d8b4fe" stroke-width="2"/>
    <rect width="400" height="35" rx="6" fill="#f3e8ff"/>
    <text x="15" y="23" font-weight="bold" fill="#6b21a8">Tangri 4-Variable KFRE Reference Calculator</text>
    <text x="15" y="60" fill="#334155" font-weight="bold">Predictive Variables:</text>
    <text x="15" y="78" fill="#64748b" font-size="11">Age, Biological Sex, eGFR (CKD-EPI), log(UACR)</text>
    <text x="15" y="105" fill="#334155" font-weight="bold">Regional Calibration Baselines:</text>
    <text x="15" y="123" fill="#64748b" font-size="11">- North American Cohort (S0_2yr = 0.9751, S0_5yr = 0.8996)</text>
    <text x="15" y="141" fill="#64748b" font-size="11">- Non-North American Recalibration (broad multinational)</text>
    <text x="15" y="165" fill="#b91c1c" font-weight="bold">Strict Eligibility Guardrail (DISC-05):</text>
    <text x="15" y="185" fill="#dc2626" font-size="11">Only applicable for confirmed G3-G5 (eGFR &lt; 60 mL/min/1.73m2).</text>
    <text x="15" y="202" fill="#dc2626" font-size="11">If eGFR &gt;= 60, automated risk calculation is safely withheld.</text>

    <!-- Right: Trajectory & Survival -->
    <g transform="translate(430, 0)">
      <rect width="410" height="220" rx="6" fill="#ffffff" stroke="#d8b4fe" stroke-width="2"/>
      <rect width="410" height="35" rx="6" fill="#f3e8ff"/>
      <text x="15" y="23" font-weight="bold" fill="#6b21a8">Longitudinal Trajectory &amp; Survival Foundation</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">eGFR Slope Trajectory Models:</text>
      <text x="15" y="78" fill="#64748b" font-size="11">- Ordinary Least Squares (OLS) annualized decline (mL/min/yr)</text>
      <text x="15" y="96" fill="#64748b" font-size="11">- Linear Mixed-Effects Model (LMM) with Best Linear Unbiased</text>
      <text x="15" y="112" fill="#64748b" font-size="11">  Predictor (BLUP) shrinkage for sparse visit histories</text>
      <text x="15" y="138" fill="#334155" font-weight="bold">Survival Analysis Framework (Deferred Status):</text>
      <text x="15" y="156" fill="#64748b" font-size="11">- Cox Proportional Hazards baseline &amp; Random Survival Forest</text>
      <text x="15" y="174" fill="#64748b" font-size="11">- Aalen-Johansen competing-risk cumulative incidence</text>
      <text x="15" y="195" fill="#7e22ce" font-weight="bold">Model Training Deferred Pending Approved CRIC DUA</text>
    </g>
  </g>

  <!-- Bottom Banner -->
  <rect x="30" y="355" width="840" height="135" rx="6" fill="#ffffff" stroke="#cbd5e1"/>
  <text x="50" y="380" font-family="system-ui, sans-serif" font-size="13" font-weight="bold" fill="#1e293b">Scientific Integrity Boundary &amp; No-Synthetic-Training Guardrail:</text>
  <text x="50" y="405" fill="#475569" font-family="system-ui, sans-serif" font-size="12">Synthetic longitudinal sequences are generated strictly for deterministic unit testing of algorithms.</text>
  <text x="50" y="425" fill="#475569" font-family="system-ui, sans-serif" font-size="12">Survival models (Cox PH, RSF) are NEVER fitted on synthetic data. Real clinical predictions are deferred</text>
  <text x="50" y="445" fill="#475569" font-family="system-ui, sans-serif" font-size="12">until institutional data-use agreements for longitudinal cohorts (e.g., CRIC) are finalized.</text>
  <text x="50" y="465" fill="#6b21a8" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Status: DEFERRED_PENDING_APPROVED_COHORT (Enforced in code and UI).</text>
</svg>"""

write_svg("engine3_architecture.svg", svg4)

# 5. Unified Assessment Workflow
svg5 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 480" width="100%" height="100%">
  <rect width="960" height="480" fill="#f8fafc"/>
  <rect x="20" y="20" width="920" height="55" rx="6" fill="#0f172a"/>
  <text x="40" y="53" fill="#ffffff" font-family="system-ui, sans-serif" font-size="18" font-weight="bold">Unified Multi-Engine Assessment &amp; Discrepancy Synthesis Workflow</text>

  <!-- Flowchart Steps -->
  <g transform="translate(30, 100)" font-family="system-ui, sans-serif" font-size="12">
    <!-- Step 1 -->
    <rect width="160" height="130" rx="6" fill="#ffffff" stroke="#64748b" stroke-width="1.5"/>
    <rect width="160" height="30" rx="6" fill="#f1f5f9"/>
    <text x="12" y="20" font-weight="bold" fill="#1e293b">1. Patient Input</text>
    <text x="12" y="50" fill="#475569">Demographics</text>
    <text x="12" y="70" fill="#475569">Serum Creatinine</text>
    <text x="12" y="90" fill="#475569">UACR &amp; 10 Biomarkers</text>
    <text x="12" y="110" fill="#475569">Longitudinal Visits</text>

    <!-- Arrow -->
    <path d="M 165 65 L 195 65" stroke="#0f172a" stroke-width="2" fill="none"/>

    <!-- Step 2 -->
    <g transform="translate(200, 0)">
      <rect width="160" height="130" rx="6" fill="#ffffff" stroke="#64748b" stroke-width="1.5"/>
      <rect width="160" height="30" rx="6" fill="#f1f5f9"/>
      <text x="12" y="20" font-weight="bold" fill="#1e293b">2. Quality Gate</text>
      <text x="12" y="50" fill="#475569">Unit conversion</text>
      <text x="12" y="70" fill="#475569">Biological bounds</text>
      <text x="12" y="90" fill="#475569">CRI Score &gt;= 0.60?</text>
      <text x="12" y="110" fill="#dc2626" font-size="11">Else Safe Abstain</text>
    </g>

    <!-- Arrow -->
    <path d="M 365 65 L 395 65" stroke="#0f172a" stroke-width="2" fill="none"/>

    <!-- Step 3: 3 parallel engines -->
    <g transform="translate(400, 0)">
      <rect width="210" height="130" rx="6" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
      <rect width="210" height="30" rx="6" fill="#dbeafe"/>
      <text x="12" y="20" font-weight="bold" fill="#1e40af">3. Parallel Execution</text>
      <text x="12" y="50" fill="#1e40af" font-size="11">- Engine 1: Screening Risk</text>
      <text x="12" y="75" fill="#15803d" font-size="11">- Engine 2: KDIGO CGA Matrix</text>
      <text x="12" y="100" fill="#7e22ce" font-size="11">- Engine 3: KFRE Progression</text>
    </g>

    <!-- Arrow -->
    <path d="M 615 65 L 645 65" stroke="#0f172a" stroke-width="2" fill="none"/>

    <!-- Step 4: Discrepancy Engine -->
    <g transform="translate(650, 0)">
      <rect width="240" height="130" rx="6" fill="#fffbeb" stroke="#f59e0b" stroke-width="1.5"/>
      <rect width="240" height="30" rx="6" fill="#fef3c7"/>
      <text x="12" y="20" font-weight="bold" fill="#92400e">4. Discrepancy Auditing</text>
      <text x="12" y="50" fill="#b45309" font-size="11">DISC-01: Low Risk vs Severe CGA</text>
      <text x="12" y="70" fill="#b45309" font-size="11">DISC-02: High Risk vs Normal CGA</text>
      <text x="12" y="90" fill="#b45309" font-size="11">DISC-03: Single Visit Chronicity</text>
      <text x="12" y="110" fill="#b45309" font-size="11">DISC-05: KFRE eGFR &gt;= 60 Gate</text>
    </g>
  </g>

  <!-- Output Delivery Block -->
  <g transform="translate(30, 260)">
    <rect width="890" height="180" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
    <text x="30" y="35" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#1e293b">5. Unified Clinical Assessment Synthesis &amp; Export Layer</text>
    <text x="30" y="65" font-family="system-ui, sans-serif" font-size="12" fill="#475569">&#10004; UnifiedAssessmentResponse Dataclass combining E1, E2, E3 findings and flags</text>
    <text x="30" y="90" font-family="system-ui, sans-serif" font-size="12" fill="#475569">&#10004; Interactive Streamlit Point-of-Care Display with side-by-side risk cards &amp; discrepancy alerts</text>
    <text x="30" y="115" font-family="system-ui, sans-serif" font-size="12" fill="#475569">&#10004; Multi-channel medical export: Clean vector PDF, machine-readable JSON, sanitized CSV (CWE-1236)</text>
    <text x="30" y="140" font-family="system-ui, sans-serif" font-size="12" fill="#475569">&#10004; Unmistakable demonstration watermark on synthetic preset evaluations</text>
  </g>
</svg>"""

write_svg("unified_assessment_workflow.svg", svg5)

# 6. Clinical Reliability & Abstention Workflow
svg6 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" width="100%" height="100%">
  <rect width="900" height="500" fill="#f8fafc"/>
  <rect x="20" y="20" width="860" height="55" rx="6" fill="#b91c1c"/>
  <text x="40" y="53" fill="#ffffff" font-family="system-ui, sans-serif" font-size="18" font-weight="bold">CD-CIRPVM: Clinical Reliability &amp; Safe Abstention Mechanism</text>

  <g transform="translate(30, 100)" font-family="system-ui, sans-serif" font-size="12">
    <!-- Box 1 -->
    <rect width="250" height="180" rx="6" fill="#ffffff" stroke="#fca5a5" stroke-width="1.5"/>
    <rect width="250" height="35" rx="6" fill="#fee2e2"/>
    <text x="15" y="23" font-weight="bold" fill="#991b1b">Magnitude-Inferred Units (MIDR)</text>
    <text x="15" y="60" fill="#334155" font-weight="bold">Automatic Unit Detection:</text>
    <text x="15" y="80" fill="#64748b" font-size="11">Creatinine: &gt; 30 umol/L -&gt; mg/dL</text>
    <text x="15" y="98" fill="#64748b" font-size="11">Hemoglobin: &gt; 25 g/L -&gt; g/dL</text>
    <text x="15" y="116" fill="#64748b" font-size="11">Glucose: &lt; 25 mmol/L -&gt; mg/dL</text>
    <text x="15" y="145" fill="#15803d" font-weight="bold">Zero Silent Coercion</text>
    <text x="15" y="163" fill="#64748b" font-size="11">Preserves clinical provenance</text>

    <!-- Box 2 -->
    <g transform="translate(280, 0)">
      <rect width="260" height="180" rx="6" fill="#ffffff" stroke="#fca5a5" stroke-width="1.5"/>
      <rect width="260" height="35" rx="6" fill="#fee2e2"/>
      <text x="15" y="23" font-weight="bold" fill="#991b1b">Clinical Reliability Index (CRI)</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">Continuous Score [0.0 - 1.0]:</text>
      <text x="15" y="80" fill="#64748b" font-size="11">Penalizes missing core biomarkers</text>
      <text x="15" y="98" fill="#64748b" font-size="11">Penalizes physiological anomalies</text>
      <text x="15" y="125" fill="#334155" font-weight="bold">Threshold Gating:</text>
      <text x="15" y="145" fill="#15803d" font-weight="bold">CRI &gt;= 0.60: Valid for prediction</text>
      <text x="15" y="163" fill="#dc2626" font-weight="bold">CRI &lt; 0.60: MANDATORY ABSTAIN</text>
    </g>

    <!-- Box 3 -->
    <g transform="translate(570, 0)">
      <rect width="260" height="180" rx="6" fill="#ffffff" stroke="#fca5a5" stroke-width="1.5"/>
      <rect width="260" height="35" rx="6" fill="#fee2e2"/>
      <text x="15" y="23" font-weight="bold" fill="#991b1b">Conformal Prediction &amp; Abstain</text>
      <text x="15" y="60" fill="#334155" font-weight="bold">Inductive Conformal Set:</text>
      <text x="15" y="80" fill="#64748b" font-size="11">Prediction set C_alpha {0}, {1}, or {0,1}</text>
      <text x="15" y="105" fill="#334155" font-weight="bold">Epistemic Uncertainty Gate:</text>
      <text x="15" y="125" fill="#64748b" font-size="11">If prediction set is {0, 1}:</text>
      <text x="15" y="145" fill="#dc2626" font-weight="bold">Decision: SAFE ABSTAIN</text>
      <text x="15" y="163" fill="#64748b" font-size="11">Withholds diagnosis on ambiguous cases</text>
    </g>
  </g>

  <!-- Bottom Details -->
  <rect x="30" y="310" width="830" height="160" rx="6" fill="#ffffff" stroke="#cbd5e1"/>
  <text x="50" y="340" font-family="system-ui, sans-serif" font-size="13" font-weight="bold" fill="#1e293b">Core Clinical Safety Principle: "Never Silently Replace Lab Gaps with Normal Values"</text>
  <text x="50" y="365" fill="#475569" font-family="system-ui, sans-serif" font-size="12">Conventional machine learning pipelines silently impute missing biomarkers with median/mode healthy values</text>
  <text x="50" y="385" fill="#475569" font-family="system-ui, sans-serif" font-size="12">(e.g., serum creatinine = 1.0 mg/dL, albumin = 0), generating artificially low risk estimates for sick patients.</text>
  <text x="50" y="405" fill="#475569" font-family="system-ui, sans-serif" font-size="12">NEFROAI-X explicitly computes panel completeness, flags missing biomarkers with an amber alert banner,</text>
  <text x="50" y="425" fill="#475569" font-family="system-ui, sans-serif" font-size="12">penalizes the Clinical Reliability Index, and abstains from automated diagnosis when data quality is insufficient.</text>
  <text x="50" y="450" fill="#b91c1c" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Guarantees safety in point-of-care emergency and outpatient clinical screening.</text>
</svg>"""

write_svg("clinical_reliability_abstention_workflow.svg", svg6)

# 7. Docker Deployment Architecture
svg7 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 520" width="100%" height="100%">
  <rect width="920" height="520" fill="#f8fafc"/>
  <rect x="20" y="20" width="880" height="55" rx="6" fill="#0284c7"/>
  <text x="40" y="53" fill="#ffffff" font-family="system-ui, sans-serif" font-size="18" font-weight="bold">NEFROAI-X: Docker Containerization &amp; Deployment Topology</text>

  <!-- Host Box -->
  <rect x="30" y="95" width="860" height="390" rx="8" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.5"/>
  <text x="50" y="125" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#334155">Host Operating System (Developer / Research Workstation)</text>

  <!-- Browser -->
  <g transform="translate(60, 150)">
    <rect width="200" height="100" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
    <text x="15" y="30" font-family="system-ui, sans-serif" font-size="13" font-weight="bold" fill="#0f172a">Local Web Browser</text>
    <text x="15" y="55" font-family="system-ui, sans-serif" font-size="12" fill="#2563eb">http://localhost:8501</text>
    <text x="15" y="75" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">Loopback-only access</text>
  </g>

  <!-- Host Port Guard -->
  <g transform="translate(290, 175)">
    <path d="M 0 25 L 50 25" stroke="#0284c7" stroke-width="3" fill="none"/>
    <rect x="50" y="0" width="140" height="50" rx="6" fill="#e0f2fe" stroke="#0284c7"/>
    <text x="60" y="22" font-family="system-ui, sans-serif" font-size="11" font-weight="bold" fill="#0369a1">Host Port Binding</text>
    <text x="60" y="38" font-family="system-ui, sans-serif" font-size="11" fill="#0284c7">127.0.0.1:8501</text>
    <path d="M 190 25 L 240 25" stroke="#0284c7" stroke-width="3" fill="none"/>
  </g>

  <!-- Container Box -->
  <g transform="translate(560, 140)">
    <rect width="300" height="320" rx="6" fill="#ffffff" stroke="#0284c7" stroke-width="2"/>
    <rect width="300" height="35" rx="6" fill="#e0f2fe"/>
    <text x="15" y="23" font-family="system-ui, sans-serif" font-size="13" font-weight="bold" fill="#0369a1">nefroai-x Container (python:3.10-slim)</text>

    <text x="15" y="60" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="#334155">Security Configuration:</text>
    <text x="15" y="78" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">- Non-root User: nefroai (uid 1001)</text>
    <text x="15" y="94" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">- Internal listener: 0.0.0.0:8501</text>
    <text x="15" y="110" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">- Limits: 2.0 CPUs, 2.0 GB RAM</text>
    <text x="15" y="126" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">- Read-only root system files</text>

    <text x="15" y="155" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="#334155">Health Check Probe:</text>
    <text x="15" y="173" font-family="system-ui, sans-serif" font-size="11" fill="#15803d">curl -f http://127.0.0.1:8501/_stcore/health</text>
    <text x="15" y="189" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">Interval: 30s | Retries: 3 | Start: 60s</text>

    <text x="15" y="215" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="#334155">Named Persistent Volumes:</text>
    <text x="15" y="233" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">- nefroai_reports -&gt; /app/reports</text>
    <text x="15" y="249" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">- nefroai_runs -&gt; /app/runs/explainability</text>

    <text x="15" y="280" font-family="system-ui, sans-serif" font-size="11" font-weight="bold" fill="#b91c1c">Air-Gapped: Zero Public Routing</text>
  </g>

  <!-- Test Container Box -->
  <g transform="translate(60, 280)">
    <rect width="200" height="140" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
    <text x="15" y="25" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="#0f172a">nefroai-test (Test Profile)</text>
    <text x="15" y="50" font-family="system-ui, sans-serif" font-size="11" fill="#475569">- docker compose run</text>
    <text x="15" y="68" font-family="system-ui, sans-serif" font-size="11" fill="#475569">- Executes full pytest suite</text>
    <text x="15" y="86" font-family="system-ui, sans-serif" font-size="11" fill="#475569">- 349 unit/integration tests</text>
    <text x="15" y="104" font-family="system-ui, sans-serif" font-size="11" fill="#15803d">&#10004; Zero UI overhead</text>
    <text x="15" y="122" font-family="system-ui, sans-serif" font-size="11" fill="#64748b">- Clean exit on complete</text>
  </g>
</svg>"""

write_svg("docker_deployment_architecture.svg", svg7)

print("All 7 architecture SVGs successfully generated in docs/images/")
