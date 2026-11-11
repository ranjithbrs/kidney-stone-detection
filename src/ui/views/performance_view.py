"""Model Performance, Calibration, Subgroup Audit & Feature Stability View."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
    backtest_egfr_trajectory,
)
from src.clinical.stacking_ensemble import get_stacking_ensemble
from src.feature_selection import FeatureSelectionPipeline


@st.cache_resource
def _load_cached_stacking() -> Any:
    """Load or build cached leak-free 4-family StackingClinicalEnsemble."""
    return get_stacking_ensemble()


@st.cache_data(show_spinner="Evaluating 5-fold inner CV feature selection stability...")
def _load_cached_cv_stability() -> Dict[str, Any]:
    """Compute leak-free 5-fold feature selection stability (excluding test split)."""
    fsp = FeatureSelectionPipeline(random_state=42)
    return fsp.evaluate_cv_selection_stability(top_k=10, n_splits=5)


def _format_ci(ci: Any) -> str:
    if isinstance(ci, (list, tuple)) and len(ci) == 2:
        return f"[{ci[0]:.3f}, {ci[1]:.3f}]"
    return "N/A"


def render_performance_view() -> None:
    """Render comprehensive model benchmark, calibration, subgroup, and backtest metrics."""
    st.markdown("## 📊 Model Performance, Calibration & Longitudinal Backtest")
    st.markdown(
        "Evaluates the 4-family leak-free Stacking Ensemble (`Random Forest` + `XGBoost` + `SVM-RBF` + `ANN/MLP` "
        "with `LogisticRegression` meta-learner), Precision-Recall, Calibration curves, bootstrap 95% confidence "
        "intervals, subgroup slices, and 5-method cross-validated biomarker stability."
    )
    st.caption(
        "Clinical Integrity Guard: All preprocessing, SMOTE rebalancing, hyperparameter tuning, OOF conformal "
        "quantiles, and feature rankings are fitted strictly on the 320-patient UCI CKD training partition. "
        "Evaluation metrics reflect the untouched 80-patient held-out test partition and should not be interpreted "
        "as multi-center clinical certification."
    )

    try:
        ensemble = _load_cached_stacking()
        report = ensemble.evaluation_report
    except Exception as exc:
        st.error(f"Unable to initialize StackingClinicalEnsemble report: {exc}")
        return

    models_dict: Dict[str, Dict[str, Any]] = report.get("models", {})
    stack_res = models_dict.get("Stacking Ensemble (Meta-LR)", {})

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Train / Held-Out Split", f"{report.get('train_samples', 320)} / {report.get('test_samples', 80)}")
    with k2:
        st.metric("Stacking Macro-F1", f"{stack_res.get('macro_f1', 0.0):.4f}", _format_ci(stack_res.get("bootstrap_ci95", {}).get("macro_f1_ci95")))
    with k3:
        st.metric("Stacking PR-AUC", f"{stack_res.get('pr_auc', 0.0):.4f}", _format_ci(stack_res.get("bootstrap_ci95", {}).get("pr_auc_ci95")))
    with k4:
        st.metric("Stacking Brier Score", f"{stack_res.get('brier_score', 0.0):.4f}", "Lowest Error")
    with k5:
        xgb_badge = "XGBoost" if report.get("xgboost_active") else "HistGradientBoost"
        st.metric("Boosting Engine", xgb_badge, "4-Family Stack")

    tab_bench, tab_sub_bt, tab_fs = st.tabs([
        "🏆 Multi-Model Benchmark, PR & Calibration",
        "🩺 Subgroups & eGFR Trajectory Backtest",
        "🧬 5-Method Feature Selection Stability",
    ])

    with tab_bench:
        st.subheader("Held-Out Test Partition Comparison (N = 80, Leak-Free Pipelines)")
        table_rows = []
        for m_name, m in models_dict.items():
            ci = m.get("bootstrap_ci95", {})
            table_rows.append({
                "Architecture": m_name,
                "Accuracy": f"{m['accuracy'] * 100:.2f}%",
                "Precision": f"{m['precision']:.4f}",
                "Sensitivity": f"{m['sensitivity']:.4f}",
                "Specificity": f"{m['specificity']:.4f}",
                "Macro-F1": f"{m['macro_f1']:.4f}",
                "ROC-AUC (95% CI)": f"{m['roc_auc']:.4f} {_format_ci(ci.get('roc_auc_ci95'))}",
                "PR-AUC (95% CI)": f"{m['pr_auc']:.4f} {_format_ci(ci.get('pr_auc_ci95'))}",
                "Brier Score": f"{m['brier_score']:.4f}",
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

        # Meta-learner log-odds coefficients
        meta_w = report.get("meta_learner_weights", {})
        if meta_w:
            st.markdown("#### Logistic Regression Meta-Learner Blending Weights (Log-Odds Coefficients)")
            mw_cols = st.columns(len(meta_w))
            for idx, (fam_name, coef) in enumerate(meta_w.items()):
                with mw_cols[idx]:
                    st.metric(fam_name, f"{coef:+.4f}", "OOF Meta Weight")

        # Curves row: ROC, PR, Calibration
        c1, c2, c3 = st.columns(3)
        palette = ["#0f4c81", "#059669", "#d97706", "#7c3aed", "#dc2626", "#0284c7"]

        with c1:
            fig_roc, ax_roc = plt.subplots(figsize=(5.0, 4.0))
            for idx, (m_name, m) in enumerate(models_dict.items()):
                rc = m.get("roc_curve", {})
                ax_roc.plot(rc.get("fpr", []), rc.get("tpr", []), label=f"{m_name} ({m['roc_auc']:.3f})", color=palette[idx % len(palette)], linewidth=1.8)
            ax_roc.plot([0, 1], [0, 1], "--", color="#94a3b8", linewidth=1.0)
            ax_roc.set_title("Multi-Model ROC Curve")
            ax_roc.set_xlabel("False Positive Rate")
            ax_roc.set_ylabel("True Positive Rate")
            ax_roc.legend(fontsize=7, loc="lower right")
            ax_roc.grid(alpha=0.25)
            fig_roc.tight_layout()
            st.pyplot(fig_roc)
            plt.close(fig_roc)

        with c2:
            fig_pr, ax_pr = plt.subplots(figsize=(5.0, 4.0))
            for idx, (m_name, m) in enumerate(models_dict.items()):
                pc = m.get("pr_curve", {})
                ax_pr.plot(pc.get("recall", []), pc.get("precision", []), label=f"{m_name} ({m['pr_auc']:.3f})", color=palette[idx % len(palette)], linewidth=1.8)
            ax_pr.set_title("Precision-Recall Curve (PR-AUC)")
            ax_pr.set_xlabel("Recall (Sensitivity)")
            ax_pr.set_ylabel("Precision (PPV)")
            ax_pr.legend(fontsize=7, loc="lower left")
            ax_pr.grid(alpha=0.25)
            fig_pr.tight_layout()
            st.pyplot(fig_pr)
            plt.close(fig_pr)

        with c3:
            fig_cal, ax_cal = plt.subplots(figsize=(5.0, 4.0))
            ax_cal.plot([0, 1], [0, 1], "--", color="#64748b", label="Perfect Calibration")
            for idx, (m_name, m) in enumerate(models_dict.items()):
                cc = m.get("calibration_curve", {})
                if cc.get("prob_pred") and cc.get("prob_true"):
                    ax_cal.plot(cc["prob_pred"], cc["prob_true"], "o-", label=f"{m_name} (Brier={m['brier_score']:.4f})", color=palette[idx % len(palette)], linewidth=1.5, markersize=4)
            ax_cal.set_title("Calibration Reliability Diagram")
            ax_cal.set_xlabel("Mean Predicted Probability")
            ax_cal.set_ylabel("Empirical Positive Fraction")
            ax_cal.legend(fontsize=7, loc="upper left")
            ax_cal.grid(alpha=0.25)
            fig_cal.tight_layout()
            st.pyplot(fig_cal)
            plt.close(fig_cal)

        # Confusion Matrix inspector
        if models_dict:
            sel_cm_model = st.selectbox("Inspect Held-Out Confusion Matrix", options=list(models_dict.keys()), index=len(models_dict) - 1)
            cm_d = models_dict[sel_cm_model].get("confusion_matrix", {})
            cm_mat = np.array([[cm_d.get("tn", 0), cm_d.get("fp", 0)], [cm_d.get("fn", 0), cm_d.get("tp", 0)]])
            fig_cm, ax_cm = plt.subplots(figsize=(4.2, 3.2))
            ax_cm.imshow(cm_mat, cmap="Blues")
            ax_cm.set_xticks([0, 1])
            ax_cm.set_yticks([0, 1])
            ax_cm.set_xticklabels(["Pred Healthy (0)", "Pred CKD (1)"])
            ax_cm.set_yticklabels(["Actual Healthy (0)", "Actual CKD (1)"])
            for (r, c), val in np.ndenumerate(cm_mat):
                ax_cm.text(c, r, str(val), ha="center", va="center", fontsize=12, fontweight="bold", color="#ffffff" if val > cm_mat.max() / 2 else "#0f172a")
            ax_cm.set_title(f"{sel_cm_model} Confusion Matrix (N=80)")
            fig_cm.tight_layout()
            st.pyplot(fig_cm)
            plt.close(fig_cm)

    with tab_sub_bt:
        st.subheader("Clinical Subgroup Performance Audit (Stacking Ensemble)")
        sub_rows = report.get("subgroup_analysis", [])
        if sub_rows:
            st.dataframe(pd.DataFrame(sub_rows), use_container_width=True)
        else:
            st.info("No subgroup metadata available.")

        st.markdown("---")
        st.subheader("Engine 3 Walk-Forward eGFR Trajectory Backtest (`MAE` / `RMSE` / `R²`)")

        resp = st.session_state.get("latest_unified_response")
        active_bt = resp.engine3_result.trajectory_backtest if (resp and resp.engine3_result) else None

        if active_bt and active_bt.get("eligible"):
            st.markdown(f"#### Active Patient Trajectory Backtest (`{resp.patient_id}`)")
            bt_to_plot = active_bt
            is_demo_bt = False
        else:
            st.markdown("#### Illustrative Synthetic Benchmark Trajectory Backtest (5 Visits, 18 Months)")
            st.caption(
                "No active longitudinal patient trajectory loaded yet; displaying a synthetic demonstration curve. "
                "This illustrative series is strictly for walk-forward regression verification."
            )
            demo_obs = [
                ClinicalObservation(timestamp=datetime(2024, 7, 1, tzinfo=timezone.utc), serum_creatinine=1.20, uacr=45.0),
                ClinicalObservation(timestamp=datetime(2024, 10, 15, tzinfo=timezone.utc), serum_creatinine=1.32, uacr=60.0),
                ClinicalObservation(timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc), serum_creatinine=1.45, uacr=82.0),
                ClinicalObservation(timestamp=datetime(2025, 6, 15, tzinfo=timezone.utc), serum_creatinine=1.58, uacr=110.0),
                ClinicalObservation(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), serum_creatinine=1.74, uacr=145.0),
            ]
            demo_rec = LongitudinalPatientRecord(
                patient_id="SYNTHETIC_DEMO_BT",
                age_baseline=62.0,
                sex="male",
                observations=demo_obs,
                is_synthetic=True,
                provenance="SYNTHETIC_DEMONSTRATION",
            )
            bt_to_plot = backtest_egfr_trajectory(demo_rec)
            is_demo_bt = True

        if bt_to_plot.get("eligible"):
            bc1, bc2, bc3, bc4 = st.columns(4)
            with bc1:
                st.metric("Evaluated Walk-Forward Steps", bt_to_plot.get("evaluated_steps", 0))
            with bc2:
                st.metric("MAE (mL/min/1.73m²)", f"{bt_to_plot.get('mae', 0.0):.3f}")
            with bc3:
                st.metric("RMSE (mL/min/1.73m²)", f"{bt_to_plot.get('rmse', 0.0):.3f}")
            with bc4:
                r2v = bt_to_plot.get("r2")
                st.metric("Out-of-Time R²", f"{r2v:.4f}" if r2v is not None else "N/A")

            act = bt_to_plot.get("actual_values", [])
            prd = bt_to_plot.get("predicted_values", [])
            if act and prd:
                fig_bt, ax_bt = plt.subplots(figsize=(6.5, 3.2))
                steps = list(range(1, len(act) + 1))
                ax_bt.plot(steps, act, "o-", label="Observed Future eGFR", color="#0f4c81", linewidth=2.0)
                ax_bt.plot(steps, prd, "s--", label="Walk-Forward Expanding OLS Forecast", color="#d97706", linewidth=2.0)
                ax_bt.set_xticks(steps)
                ax_bt.set_xlabel("Expanding Validation Visit Step")
                ax_bt.set_ylabel("eGFR (mL/min/1.73m²)")
                ax_bt.set_title("Walk-Forward Observed vs. Forecasted eGFR" + (" [Synthetic Demo]" if is_demo_bt else ""))
                ax_bt.legend()
                ax_bt.grid(alpha=0.25)
                fig_bt.tight_layout()
                st.pyplot(fig_bt)
                plt.close(fig_bt)

    with tab_fs:
        st.subheader("Fold-Safe 5-Method Consensus Stability (MI + ANOVA + RF + RFE + TreeSHAP)")
        try:
            stab = _load_cached_cv_stability()
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                st.metric("Mean Pairwise Jaccard Stability", f"{stab.get('mean_pairwise_jaccard', 0.0):.4f}")
            with fc2:
                st.metric("Inner Training Partition", f"N={stab.get('train_partition_size', 320)}", f"{stab.get('n_splits', 5)}-Fold CV")
            with fc3:
                st.metric("Held-Out Test Leakage", "EXCLUDED" if stab.get("held_out_test_excluded") else "CHECK")

            st.markdown(f"**Consensus Top-{stab.get('top_k', 10)} Features by Cross-Fold Frequency:** `{stab.get('consensus_by_frequency', [])}`")

            freq_map = stab.get("feature_frequencies", {})
            if freq_map:
                freq_df = pd.DataFrame([
                    {"Biomarker": feat, "Folds Selected (out of 5)": cnt, "Selection Stability (%)": round(cnt / stab.get("n_splits", 5) * 100.0, 1)}
                    for feat, cnt in freq_map.items()
                ])
                st.dataframe(freq_df, use_container_width=True)

            fold_lists = stab.get("fold_selections", [])
            if fold_lists:
                with st.expander("📂 Per-Fold Selected Feature Sets (Strict Inner-Fold Fit)"):
                    for i, flist in enumerate(fold_lists, start=1):
                        st.markdown(f"- **Fold {i}:** `{flist}`")
        except Exception as exc:
            st.warning(f"Could not compute cross-validated selection stability: {exc}")

