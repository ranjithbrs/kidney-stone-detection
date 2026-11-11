"""Clinical visualisations including KDIGO 6x3 heatmaps, longitudinal trajectories, and XAI charts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import shap
import streamlit as st


def render_kdigo_matrix(
    gfr_cat: Optional[str] = None,
    alb_cat: Optional[str] = None,
    figsize: tuple = (7.5, 4.5),
) -> plt.Figure:
    """Generate the official KDIGO 6x3 prognostic color matrix highlighting the patient's stage."""
    g_stages = ["G1", "G2", "G3a", "G3b", "G4", "G5"]
    g_labels = [
        "G1 (≥90 Normal/High)",
        "G2 (60-89 Mild)",
        "G3a (45-59 Mild-Mod)",
        "G3b (30-44 Mod-Severe)",
        "G4 (15-29 Severe)",
        "G5 (<15 Kidney Failure)"
    ]
    a_stages = ["A1", "A2", "A3"]
    a_labels = [
        "A1: Normal/Mild\n(<30 mg/g)",
        "A2: Moderate\n(30-300 mg/g)",
        "A3: Severe\n(>300 mg/g)"
    ]

    # Standard KDIGO color matrix (0=Low/Green, 1=Mod/Yellow, 2=High/Orange, 3=VeryHigh/Red)
    # Rows: G1 to G5, Columns: A1 to A3
    kdigo_grid = np.array([
        [0, 1, 2],  # G1
        [0, 1, 2],  # G2
        [1, 2, 3],  # G3a
        [2, 3, 3],  # G3b
        [3, 3, 3],  # G4
        [3, 3, 3],  # G5
    ])

    color_palette = {
        0: "#86efac",  # Low risk - light green
        1: "#fde047",  # Moderate risk - yellow
        2: "#fdba74",  # High risk - orange
        3: "#fca5a5",  # Very high risk - red
    }

    fig, ax = plt.subplots(figsize=figsize, dpi=120)

    # Draw cells
    for r in range(6):
        for c in range(3):
            val = kdigo_grid[r, c]
            cell_color = color_palette[val]
            rect = patches.Rectangle((c, 5 - r), 1, 1, facecolor=cell_color, edgecolor="#cbd5e1", linewidth=1.5)
            ax.add_patch(rect)

            # Label text inside cell
            cell_text = ["Low", "Mod", "High", "Very High"][val]
            ax.text(c + 0.5, 5 - r + 0.5, cell_text, ha="center", va="center", fontsize=9, fontweight="bold", color="#1e293b")

    # Highlight patient coordinate if valid
    if gfr_cat in g_stages and alb_cat in a_stages:
        r_idx = g_stages.index(gfr_cat)
        c_idx = a_stages.index(alb_cat)
        # Highlight border
        highlight = patches.Rectangle(
            (c_idx, 5 - r_idx), 1, 1,
            facecolor="none", edgecolor="#0f4c81", linewidth=4.0, linestyle="-"
        )
        ax.add_patch(highlight)
        # Add target marker
        ax.text(c_idx + 0.5, 5 - r_idx + 0.82, "★ PATIENT", ha="center", va="center", fontsize=9, fontweight="900", color="#0f4c81")

    ax.set_xlim(0, 3)
    ax.set_ylim(0, 6)
    ax.set_xticks([0.5, 1.5, 2.5])
    ax.set_xticklabels(a_labels, fontsize=8.5, fontweight="600")
    ax.set_yticks([5.5, 4.5, 3.5, 2.5, 1.5, 0.5])
    ax.set_yticklabels(g_labels, fontsize=8.5, fontweight="600")
    ax.set_title("KDIGO 2024 CGA Prognosis & Staging Risk Matrix", fontsize=11, fontweight="bold", color="#0f4c81", pad=12)

    plt.tight_layout()
    return fig


def render_longitudinal_timeline(
    observations: List[Dict[str, Any]],
    landmark_time: Optional[datetime] = None,
    slope: Optional[float] = None,
    lmm_slope: Optional[float] = None,
    figsize: tuple = (8.0, 5.0),
) -> plt.Figure:
    """Generate longitudinal trajectory plots for filtration (eGFR) and albuminuria (uACR)."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True, dpi=120)

    if not observations:
        ax1.text(0.5, 0.5, "No longitudinal visits recorded", ha="center", va="center", color="#64748b")
        ax2.text(0.5, 0.5, "No longitudinal visits recorded", ha="center", va="center", color="#64748b")
        return fig

    # Extract dates and metrics
    dates = []
    egfr_vals = []
    uacr_vals = []

    for obs in observations:
        d = obs.get("date")
        if isinstance(d, datetime):
            d = d.date()
        dates.append(d)

        # eGFR or estimate
        egfr = obs.get("egfr")
        if egfr is None and obs.get("scr") is not None:
            # Simple fallback display estimate if not calculated
            scr = obs.get("scr")
            egfr = round(142.0 * ((scr / 0.9) ** -1.2) * (0.9938 ** 60.0), 1)
        egfr_vals.append(egfr)
        uacr_vals.append(obs.get("uacr"))

    # Subplot 1: eGFR
    ax1.plot(dates, egfr_vals, marker="o", color="#0f4c81", linewidth=2.0, markersize=6, label="eGFR (mL/min/1.73m²)")
    ax1.axhline(60, color="#d97706", linestyle="--", alpha=0.7, label="CKD Threshold (G3a: 60)")
    ax1.axhline(15, color="#ef4444", linestyle="--", alpha=0.7, label="Kidney Failure (G5: 15)")

    if slope is not None:
        ax1.text(
            0.02, 0.08, f"OLS Slope: {slope:+.2f} mL/min/yr",
            transform=ax1.transAxes, fontsize=8.5, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#f8fafc", edgecolor="#cbd5e1")
        )

    ax1.set_ylabel("eGFR (mL/min)", fontsize=9, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=8)

    # Subplot 2: uACR
    valid_uacr_dates = [d for d, u in zip(dates, uacr_vals) if u is not None]
    valid_uacr_vals = [u for u in uacr_vals if u is not None]

    if valid_uacr_vals:
        ax2.plot(valid_uacr_dates, valid_uacr_vals, marker="s", color="#7c3aed", linewidth=1.8, markersize=5, label="uACR (mg/g)")
        ax2.axhline(30, color="#f59e0b", linestyle=":", alpha=0.7, label="Microalbuminuria (A2: 30)")
        ax2.axhline(300, color="#ef4444", linestyle=":", alpha=0.7, label="Macroalbuminuria (A3: 300)")

    ax2.set_ylabel("uACR (mg/g)", fontsize=9, fontweight="bold")
    ax2.set_xlabel("Observation Date", fontsize=9, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right", fontsize=8)

    # Landmark cut-off line
    if landmark_time is not None:
        lm_date = landmark_time.date() if hasattr(landmark_time, "date") else landmark_time
        ax1.axvline(lm_date, color="#059669", linestyle="-.", linewidth=1.5, label="Landmark Date")
        ax2.axvline(lm_date, color="#059669", linestyle="-.", linewidth=1.5)

    plt.tight_layout()
    return fig


def render_feature_attributions_chart(
    attributions: Optional[Dict[str, Any]],
    figsize: tuple = (6.0, 3.5),
) -> plt.Figure:
    """Generate feature leverage attribution horizontal bar chart."""
    fig, ax = plt.subplots(figsize=figsize, dpi=120)

    if not attributions:
        ax.text(0.5, 0.5, "Feature attributions unavailable", ha="center", va="center", color="#64748b")
        return fig

    feats = list(attributions.keys())
    weights = [attributions[f].get("importance_weight", 0.0) for f in feats]

    y_pos = np.arange(len(feats))
    ax.barh(y_pos, weights, color="#0f4c81", alpha=0.85, edgecolor="#0f4c81")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(feats, fontsize=8.5, fontweight="600")
    ax.invert_yaxis()
    ax.set_xlabel("Global Gini / MDI Importance Weight", fontsize=9, fontweight="bold")
    ax.set_title("Global Random Forest Feature Importance (MDI Heuristic)", fontsize=10, fontweight="bold", color="#0f4c81")
    ax.grid(True, axis="x", linestyle=":", alpha=0.5)

    plt.tight_layout()
    return fig


def render_live_treeshap_waterfall(
    shap_result: Optional[Any],
    patient_id: str = "",
    figsize: tuple = (8.5, 4.8),
) -> plt.Figure:
    """Generate a live cooperative game-theoretic TreeSHAP waterfall figure for a patient."""
    if shap_result is None or getattr(shap_result, "explanation_object", None) is None:
        fig, ax = plt.subplots(figsize=figsize, dpi=120)
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "Live TreeSHAP waterfall unavailable for this record",
            ha="center",
            va="center",
            color="#64748b",
            fontsize=10,
        )
        return fig

    fig = plt.figure(figsize=figsize, dpi=130)
    shap.plots.waterfall(
        shap_result.explanation_object,
        show=False,
        max_display=len(shap_result.feature_names),
    )
    active_fig = plt.gcf()
    active_fig.set_size_inches(*figsize)
    title_suffix = f" ({patient_id})" if patient_id else ""
    plt.title(
        f"Live TreeSHAP Local Waterfall Attribution{title_suffix}",
        fontsize=11,
        fontweight="bold",
        color="#0f4c81",
        pad=12,
    )
    plt.tight_layout()
    return active_fig
