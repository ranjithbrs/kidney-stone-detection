"""Cross-engine discrepancy reporting and clinical discordance alerts component."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from src.clinical.assessment_contracts import FindingSeverity


def render_discrepancies(discrepancies: List[Dict[str, Any]]) -> None:
    """Render cross-engine clinical discrepancy alerts with severity-coded styling."""
    if not discrepancies:
        st.success("✅ **Cross-Engine Concordance**: No conflicting diagnostic or staging findings detected across evaluated engines.")
        return

    st.markdown("### ⚠️ Cross-Engine Consistency & Clinical Discrepancy Alerts")
    st.markdown("""
    The orchestrator continuously monitors for clinical discordance across the screening, staging,
    and progression models. Transparent disagreement is highlighted below to avoid premature false assurance:
    """)

    for d in discrepancies:
        sev = d.get("severity", FindingSeverity.WARNING.value)
        disc_id = d.get("discrepancy_id", "")
        title = d.get("title", "Clinical Discrepancy")
        desc = d.get("description", "")
        action = d.get("clinical_action", "")
        engines = ", ".join(d.get("involved_engines", []))

        if sev == FindingSeverity.CRITICAL.value:
            st.error(f"""
            🚨 **CRITICAL DISCREPANCY [{disc_id}]: {title}**
            
            **Involved Engines:** {engines}  
            **Finding:** {desc}  
            
            **Recommended Clinical Action:** {action}
            """)
        elif sev == FindingSeverity.WARNING.value:
            st.warning(f"""
            ⚠️ **CLINICAL ADVISORY [{disc_id}]: {title}**
            
            **Involved Engines:** {engines}  
            **Finding:** {desc}  
            
            **Recommended Clinical Action:** {action}
            """)
        else:
            st.info(f"""
            ℹ️ **SYSTEM AUDIT [{disc_id}]: {title}**
            
            **Involved Engines:** {engines}  
            **Finding:** {desc}  
            
            **Clinical Context:** {action}
            """)
