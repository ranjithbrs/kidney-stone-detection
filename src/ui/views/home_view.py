"""Home / System Overview Landing View."""

from __future__ import annotations

import streamlit as st


def render_home_view() -> None:
    """Render the modern SaaS overview dashboard without redundant headers or ASCII boxes."""
    st.markdown(
        """
        <style>
        .nx-hero-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.15rem;
        }
        @media (max-width: 980px) {
            .nx-hero-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        .nx-kpi-tile {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 0.9rem 1.05rem;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        }
        .nx-kpi-label {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #64748b;
        }
        .nx-kpi-val {
            font-size: 1.38rem;
            font-weight: 800;
            color: #0f2942;
            margin: 0.2rem 0 0.15rem 0;
        }
        .nx-kpi-note {
            font-size: 0.78rem;
            color: #475569;
        }
        .nx-eng-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1.15rem 1.2rem;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
            min-height: 245px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .nx-eng-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.65rem;
        }
        .nx-eng-title {
            font-size: 0.98rem;
            font-weight: 800;
            color: #0f2942;
            margin: 0;
        }
        .nx-chip {
            font-size: 0.67rem;
            font-weight: 700;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            letter-spacing: 0.03em;
            white-space: nowrap;
            flex-shrink: 0;
        }
        .nx-chip-green { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
        .nx-chip-amber { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
        .nx-spec-row {
            font-size: 0.84rem;
            color: #334155;
            padding: 0.28rem 0;
            border-bottom: 1px dashed #f1f5f9;
            line-height: 1.35;
        }
        .nx-spec-row:last-child { border-bottom: none; }
        .nx-flow-shell {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1.15rem 1.2rem;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
            margin-top: 0.35rem;
        }
        .nx-flow-row {
            display: flex;
            flex-wrap: wrap;
            align-items: stretch;
            justify-content: space-between;
            gap: 0.5rem;
        }
        .nx-flow-node {
            flex: 1 1 180px;
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 11px;
            padding: 0.78rem 0.85rem;
        }
        .nx-flow-step {
            font-size: 0.68rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #0e7490;
            margin-bottom: 0.2rem;
        }
        .nx-flow-name {
            font-size: 0.90rem;
            font-weight: 800;
            color: #0f2942;
            margin-bottom: 0.3rem;
        }
        .nx-flow-desc {
            font-size: 0.78rem;
            color: #475569;
            line-height: 1.35;
        }
        .nx-flow-arrow {
            display: flex;
            align-items: center;
            justify-content: center;
            color: #64748b;
            font-weight: 800;
            font-size: 1.1rem;
            padding: 0 0.1rem;
        }
        .nx-disc-strip {
            margin-top: 0.85rem;
            padding-top: 0.75rem;
            border-top: 1px solid #e2e8f0;
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            align-items: center;
        }
        .nx-disc-pill {
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 0.2rem 0.5rem;
            font-size: 0.73rem;
            font-weight: 600;
            color: #1e293b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Top KPI Overview Strip
    st.markdown(
        """
        <div class="nx-hero-grid">
            <div class="nx-kpi-tile" style="border-top: 3px solid #0f4c81;">
                <div class="nx-kpi-label">Screening Panel</div>
                <div class="nx-kpi-val">10 Biomarkers</div>
                <div class="nx-kpi-note">5-method consensus (Jaccard 0.927)</div>
            </div>
            <div class="nx-kpi-tile" style="border-top: 3px solid #059669;">
                <div class="nx-kpi-label">4-Family Stacking</div>
                <div class="nx-kpi-val">Brier 0.0014</div>
                <div class="nx-kpi-note">RF + XGBoost + SVM + ANN (N=80 test)</div>
            </div>
            <div class="nx-kpi-tile" style="border-top: 3px solid #0284c7;">
                <div class="nx-kpi-label">Uncertainty Gate</div>
                <div class="nx-kpi-val">95% Conformal</div>
                <div class="nx-kpi-note">Split &amp; Mondrian class-conditional</div>
            </div>
            <div class="nx-kpi-tile" style="border-top: 3px solid #d97706;">
                <div class="nx-kpi-label">Safety Guardrails</div>
                <div class="nx-kpi-val">DISC-01 to 10</div>
                <div class="nx-kpi-note">COH coherence, AKI guard &amp; SHA-256</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Three Engine Cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="nx-eng-card" style="border-top: 4px solid #0f4c81;">
                <div>
                    <div class="nx-eng-head">
                        <h4 class="nx-eng-title">🩺 Engine 1: CKD Screening</h4>
                        <span class="nx-chip nx-chip-green">ONLINE</span>
                    </div>
                    <div class="nx-spec-row"><b>Purpose:</b> Early non-invasive CKD vs. Healthy screening from 10 routine blood &amp; urine labs.</div>
                    <div class="nx-spec-row"><b>Models:</b> Tuned Random Forest champion + 4-Family Stacking Ensemble (RF, XGBoost, SVM, ANN).</div>
                    <div class="nx-spec-row"><b>Safety:</b> MIDR SI-unit conversion, COH-01..04 checks &amp; Mondrian abstention.</div>
                </div>
                <div style="font-size: 0.76rem; color: #64748b; margin-top: 0.65rem;">Cohort: UCI CKD (N=400, leak-free 80/20 split)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="nx-eng-card" style="border-top: 4px solid #059669;">
                <div>
                    <div class="nx-eng-head">
                        <h4 class="nx-eng-title">🔬 Engine 2: KDIGO Staging</h4>
                        <span class="nx-chip nx-chip-green">ONLINE</span>
                    </div>
                    <div class="nx-spec-row"><b>Purpose:</b> Quantitative KDIGO 2024 severity categorization (Low to Very High Risk).</div>
                    <div class="nx-spec-row"><b>Equations:</b> Race-free CKD-EPI 2021 eGFR (G1–G5) + urinary uACR grading (A1–A3).</div>
                    <div class="nx-spec-row"><b>Safeguard:</b> Flags single-timepoint exams requiring 90-day persistence confirmation.</div>
                </div>
                <div style="font-size: 0.76rem; color: #64748b; margin-top: 0.65rem;">Benchmark: NHANES 2017–2018 population context</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="nx-eng-card" style="border-top: 4px solid #7c3aed;">
                <div>
                    <div class="nx-eng-head">
                        <h4 class="nx-eng-title">📈 Engine 3: Progression</h4>
                        <span class="nx-chip nx-chip-amber">SURVIVAL GATED</span>
                    </div>
                    <div class="nx-spec-row"><b>Purpose:</b> Multi-visit kidney trend tracking &amp; 2-yr/5-yr KFRE reference risk.</div>
                    <div class="nx-spec-row"><b>Methods:</b> OLS &amp; LMM BLUP slopes, walk-forward backtest, &amp; acute AKI spike guard.</div>
                    <div class="nx-spec-row"><b>Boundary:</b> Survival ML withheld pending approved CRIC DUA cohort data.</div>
                </div>
                <div style="font-size: 0.76rem; color: #64748b; margin-top: 0.65rem;">KFRE strictly withheld when eGFR &gt;= 60</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

    # Visual End-to-End Pipeline Architecture (Clean HTML Flex Diagram)
    st.markdown(
        """
        <div class="nx-flow-shell">
            <div class="nx-section-title">System Architecture &amp; Clinical Safety Workflow</div>
            <div class="nx-section-sub">How every patient record or batch CSV flows from input validation through coordinated inference to tamper-evident output.</div>
            <div class="nx-flow-row">
                <div class="nx-flow-node" style="border-left: 4px solid #0f4c81;">
                    <div class="nx-flow-step">Stage 01</div>
                    <div class="nx-flow-name">Ingestion &amp; Schema</div>
                    <div class="nx-flow-desc">Single form presets or CSV cohort (&lt;=500 rows). Rejects non-renal datasets cleanly.</div>
                </div>
                <div class="nx-flow-arrow">→</div>
                <div class="nx-flow-node" style="border-left: 4px solid #0e7490;">
                    <div class="nx-flow-step">Stage 02</div>
                    <div class="nx-flow-name">MIDR &amp; Coherence</div>
                    <div class="nx-flow-desc">Auto-converts SI units (µmol/L, g/L, mmol/L), runs COH-01..04 invariants &amp; scores CRI.</div>
                </div>
                <div class="nx-flow-arrow">→</div>
                <div class="nx-flow-node" style="border-left: 4px solid #0284c7;">
                    <div class="nx-flow-step">Stage 03</div>
                    <div class="nx-flow-name">3 Parallel Engines</div>
                    <div class="nx-flow-desc">Engine 1 RF/Stacking risk, Engine 2 KDIGO CGA heatmap &amp; Engine 3 eGFR/AKI tracking.</div>
                </div>
                <div class="nx-flow-arrow">→</div>
                <div class="nx-flow-node" style="border-left: 4px solid #d97706;">
                    <div class="nx-flow-step">Stage 04</div>
                    <div class="nx-flow-name">Conformal &amp; DISC</div>
                    <div class="nx-flow-desc">Split &amp; Mondrian uncertainty sets, model disagreement (DISC-10) &amp; PSI/Mahalanobis drift.</div>
                </div>
                <div class="nx-flow-arrow">→</div>
                <div class="nx-flow-node" style="border-left: 4px solid #059669;">
                    <div class="nx-flow-step">Stage 05</div>
                    <div class="nx-flow-name">Arbitration &amp; Vault</div>
                    <div class="nx-flow-desc">Safety-Max escalation, SHAP/LIME/What-If XAI, PDF/CSV export &amp; SHA-256 verification.</div>
                </div>
            </div>
            <div class="nx-disc-strip">
                <span style="font-size:0.75rem; font-weight:700; color:#475569; margin-right:0.2rem;">Active Audit Rules:</span>
                <span class="nx-disc-pill">DISC-01 Missing Staging</span>
                <span class="nx-disc-pill">DISC-02 False Assurance</span>
                <span class="nx-disc-pill">DISC-03 Unproven Chronicity</span>
                <span class="nx-disc-pill">DISC-05 KFRE Scope</span>
                <span class="nx-disc-pill">DISC-06 Non-Concurrent Labs</span>
                <span class="nx-disc-pill">DISC-08 Conformal Gate</span>
                <span class="nx-disc-pill">DISC-09 Coherence Contradiction</span>
                <span class="nx-disc-pill">DISC-10 Spread / AKI Spike</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

    # Bottom Governance & Provenance Cards
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown(
            """
            <div class="nx-card" style="height: 100%;">
                <div class="nx-section-title">📚 Training &amp; Validation Provenance</div>
                <ul style="font-size: 0.85rem; color: #334155; padding-left: 1.15rem; margin: 0.45rem 0 0 0; line-height: 1.55;">
                    <li><b>UCI CKD (Dataset A):</b> 400 clinical records (250 CKD, 150 Normal) with SHA-256 protected splits.</li>
                    <li><b>NHANES 2017–2018 (Engine 2):</b> Population laboratory harmonization benchmark.</li>
                    <li><b>CRIC Longitudinal Cohort (Engine 3):</b> Gated under NIDDK DUA; synthetic fixtures are strictly for testing.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with pcol2:
        st.markdown(
            """
            <div class="nx-card" style="height: 100%;">
                <div class="nx-section-title">🛡️ Core Clinical Safety Mandates</div>
                <ul style="font-size: 0.85rem; color: #334155; padding-left: 1.15rem; margin: 0.45rem 0 0 0; line-height: 1.55;">
                    <li><b>Zero Silent Imputation:</b> Missing biomarkers are never silently filled with healthy defaults.</li>
                    <li><b>Discordance Over Consensus:</b> Screening vs. laboratory staging conflicts always alert prominently.</li>
                    <li><b>Tamper-Evident Traceability:</b> Assessments bind sanitized inputs and verdicts with SHA-256 digests.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
