"""Authenticated Patient History Store & Tamper-Evident Audit Vault View."""

from __future__ import annotations

import json
from typing import Optional

import pandas as pd
import streamlit as st

from src.clinical.attestation import verify_assessment_attestation
from src.clinical.patient_store import ClinicalHistoryStore
from src.ui.components.auth import render_auth_forms, sign_out_session


def _get_store() -> ClinicalHistoryStore:
    return ClinicalHistoryStore()


def render_history_view() -> None:
    """Render authenticated local patient history store and SHA-256 attestation verifier."""
    st.markdown("## 🗂️ Patient History & Tamper-Evident Audit Vault")
    st.markdown(
        "Persist clinical assessments locally in SQLite (`runs/local_cdss.db`) with PBKDF2 "
        "clinician authentication, multi-visit Engine 3 trajectory loading, and cryptographic SHA-256 "
        "provenance attestation verification."
    )

    store = _get_store()
    active_user: Optional[str] = st.session_state.get("auth_username")
    active_role: str = st.session_state.get("auth_role", "Researcher")
    active_name: str = st.session_state.get("auth_full_name", "Guest Researcher")

    # 1. Clinician Account Sign In / Sign Up Panel
    if active_user:
        c_prof, c_out = st.columns([3.2, 1.0])
        with c_prof:
            st.success(
                f"🔐 Authenticated locally as **{active_name}** (`@{active_user}` · Role: `{active_role}`)."
            )
        with c_out:
            if st.button("🚪 Sign Out", key="vault_sign_out", use_container_width=True):
                sign_out_session()
                st.rerun()
    else:
        with st.expander("🔐 Sign In or Create Account (PBKDF2 Protected Local Auth)", expanded=True):
            st.caption(
                "Currently running in local **Guest Session** mode. Sign in or create an account below "
                "(or via the sidebar `Sign In` / `Sign Up` buttons) to save & scope your patient histories."
            )
            render_auth_forms(store, default_mode="signin", key_prefix="vault")

    owner_scope = active_user if active_user else None

    # 2. Save Active Assessment Quick-Action
    resp = st.session_state.get("latest_unified_response")
    if resp is not None:
        st.markdown("---")
        sc1, sc2 = st.columns([2, 1])
        with sc1:
            st.info(
                f"Active session assessment `{resp.assessment_id}` for patient `{resp.patient_id}` is ready to store."
            )
        with sc2:
            if st.button("💾 Save Active Assessment Now", type="primary", use_container_width=True, key="vault_save_active"):
                row_id = store.save_assessment(
                    resp,
                    owner_username=active_user or "guest_researcher",
                )
                st.success(f"Saved snapshot #{row_id} for patient `{resp.patient_id}`.")

    # 3. Stored Assessment History Browser & Engine 3 Trajectory Loader
    st.markdown("---")
    st.subheader("📋 Saved Longitudinal Assessment History")
    f1, f2 = st.columns([2, 1])
    with f1:
        patient_filter = st.text_input("Filter by Patient ID (leave blank for all)", value="", key="vault_pt_filter")
    with f2:
        scope_mine = st.checkbox(
            "Only my saved assessments",
            value=bool(active_user),
            disabled=active_user is None,
            key="vault_scope_mine",
        )

    effective_owner = active_user if (active_user and scope_mine) else None
    rows = store.list_assessments(
        patient_id=patient_filter.strip() or None,
        owner_username=effective_owner,
        limit=100,
    )

    if not rows:
        st.info(
            "No saved clinical assessments found in `runs/local_cdss.db` matching this filter. "
            "Run an evaluation in **🩺 Patient Clinical Assessment** and click **Save Assessment**."
        )
    else:
        df_hist = pd.DataFrame(rows)
        st.dataframe(df_hist, use_container_width=True)

        unique_patients = sorted({r["patient_id"] for r in rows if r.get("patient_id")})
        lcol1, lcol2 = st.columns([2, 1])
        with lcol1:
            sel_pt = st.selectbox("Select Patient to Load Longitudinal Visits", options=unique_patients, key="vault_sel_pt")
        with lcol2:
            st.markdown("<div style='padding-top: 1.7rem;'></div>", unsafe_allow_html=True)
            if st.button("📈 Load Visits into Engine 3 Trajectory", use_container_width=True, key="vault_load_e3"):
                visits = store.load_patient_visits_for_engine3(sel_pt, owner_username=effective_owner)
                st.session_state["e3_observations"] = visits
                st.session_state["e3_patient_id"] = sel_pt
                st.success(
                    f"Loaded {len(visits)} longitudinal visit(s) for `{sel_pt}` into `st.session_state.e3_observations`. "
                    "Open **📈 Longitudinal Kidney Assessment** or **🩺 Patient Clinical Assessment** to analyze progression."
                )

        # Stored Record Integrity Verification & Payload Export
        aid_list = [r["assessment_id"] for r in rows]
        sel_aid = st.selectbox("Inspect or Verify Stored Record Attestation", options=aid_list, key="vault_sel_aid")
        payload_dict = store.get_assessment_payload(sel_aid)
        if payload_dict:
            v_ok, expected_sha, recomputed_sha = verify_assessment_attestation(payload_dict)
            if v_ok:
                st.success(f"🔐 **Integrity Verified (`SHA-256` Match)**: `{recomputed_sha}`")
            else:
                st.error(
                    f"⛔ **Attestation Mismatch**: Expected `{expected_sha}`, recomputed `{recomputed_sha}`."
                )
            dcol1, dcol2 = st.columns([1, 2])
            with dcol1:
                st.download_button(
                    label="📥 Download Stored JSON Payload",
                    data=json.dumps(payload_dict, indent=2, default=str),
                    file_name=f"nefroai_{sel_aid}.json",
                    mime="application/json",
                )
            with dcol2:
                with st.expander("Inspect Raw Attested Response JSON"):
                    st.json(payload_dict)

    # 4. External JSON Report Tamper Verification Tool
    st.markdown("---")
    st.subheader("🔍 Verify Exported JSON Report Attestation (Tamper Check)")
    st.caption(
        "Upload any NefroAI-X `.json` assessment export to verify that biomarkers, clinical results, "
        "safety arbitration tier, and discrepancy flags have not been modified post-inference."
    )
    uploaded_json = st.file_uploader("Upload NefroAI-X JSON Assessment Report", type=["json"], key="vault_json_verify")
    if uploaded_json is not None:
        try:
            parsed = json.loads(uploaded_json.getvalue().decode("utf-8"))
            ok, exp_hash, comp_hash = verify_assessment_attestation(parsed)
            if ok:
                st.success(
                    f"✅ **Authentic Unmodified Report Verified**\n\n`SHA-256`: `{comp_hash}`"
                )
            else:
                st.error(
                    f"⛔ **TAMPER DETECTED OR MISSING SIGNATURE**\n\n"
                    f"- Embedded Digest: `{exp_hash}`\n"
                    f"- Recomputed Digest: `{comp_hash}`"
                )
        except Exception as exc:
            st.error(f"Could not parse JSON report: {exc}")

