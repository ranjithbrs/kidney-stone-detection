"""Reusable Sign In / Sign Up authentication components (modal dialog + sidebar widget)."""

from __future__ import annotations

import html

import streamlit as st

from src.clinical.patient_store import ClinicalHistoryStore


def _set_authenticated_session(user_rec: dict) -> None:
    """Populate authenticated user fields cleanly in Streamlit session state."""
    st.session_state["auth_username"] = user_rec["username"]
    st.session_state["auth_full_name"] = user_rec["full_name"]
    st.session_state["auth_role"] = user_rec["role"]
    st.session_state["auth_email"] = user_rec.get("email", "")


def sign_out_session() -> None:
    """Clear authenticated user fields back to Guest Session."""
    for key in ("auth_username", "auth_full_name", "auth_role", "auth_email"):
        st.session_state.pop(key, None)


def render_auth_forms(
    store: ClinicalHistoryStore,
    default_mode: str = "signin",
    key_prefix: str = "auth",
) -> None:
    """Render tabbed Sign In and Sign Up forms backed by SQLite + PBKDF2."""
    tab_order = (
        ["📝 Create Account (Sign Up)", "🔑 Sign In"]
        if default_mode == "signup"
        else ["🔑 Sign In", "📝 Create Account (Sign Up)"]
    )
    tabs = st.tabs(tab_order)
    tab_signup = tabs[0] if default_mode == "signup" else tabs[1]
    tab_signin = tabs[1] if default_mode == "signup" else tabs[0]

    with tab_signin:
        with st.form(f"{key_prefix}_signin_form", clear_on_submit=False):
            ident = st.text_input(
                "Username or Email",
                placeholder="Enter your username or email",
                key=f"{key_prefix}_login_ident",
            )
            pw = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key=f"{key_prefix}_login_pw",
            )
            submitted_in = st.form_submit_button(
                "🔑 Sign In",
                type="primary",
                use_container_width=True,
            )
        if submitted_in:
            user_rec = store.authenticate_user(ident, pw)
            if user_rec:
                _set_authenticated_session(user_rec)
                st.success(f"Welcome back, {user_rec['full_name']}!")
                st.rerun()
            else:
                st.error("Invalid username/email or password. Please check your credentials or create an account.")

    with tab_signup:
        with st.form(f"{key_prefix}_signup_form", clear_on_submit=False):
            new_user = st.text_input(
                "Username *",
                placeholder="e.g., dr_ranjith (min 3 characters, no spaces)",
                key=f"{key_prefix}_reg_user",
            )
            c1, c2 = st.columns(2)
            with c1:
                full_name = st.text_input(
                    "Full Name *",
                    placeholder="e.g., B Ranjith",
                    key=f"{key_prefix}_reg_name",
                )
            with c2:
                role = st.selectbox(
                    "Role",
                    ["Clinician", "Nephrologist", "Researcher", "Student / Presenter"],
                    key=f"{key_prefix}_reg_role",
                )
            email = st.text_input(
                "Email (optional)",
                placeholder="name@hospital.org",
                key=f"{key_prefix}_reg_email",
            )
            p1, p2 = st.columns(2)
            with p1:
                pw1 = st.text_input(
                    "Password *",
                    type="password",
                    placeholder="Minimum 6 characters",
                    key=f"{key_prefix}_reg_pw1",
                )
            with p2:
                pw2 = st.text_input(
                    "Confirm Password *",
                    type="password",
                    placeholder="Re-enter password",
                    key=f"{key_prefix}_reg_pw2",
                )
            submitted_up = st.form_submit_button(
                "📝 Create Account & Sign In",
                type="primary",
                use_container_width=True,
            )
        if submitted_up:
            if pw1 != pw2:
                st.error("Passwords do not match. Please enter identical passwords.")
            elif not (full_name or "").strip():
                st.error("Please enter your Full Name.")
            else:
                ok, msg = store.register_user(
                    username=new_user,
                    password=pw1,
                    full_name=full_name,
                    role=role,
                    email=email,
                )
                if ok:
                    user_rec = store.authenticate_user(new_user, pw1)
                    if user_rec:
                        _set_authenticated_session(user_rec)
                    st.success(f"{msg} Signed in automatically.")
                    st.rerun()
                else:
                    st.error(msg)


@st.dialog("NEFROAI-X Account Access")
def open_auth_dialog(default_mode: str = "signin") -> None:
    """Open floating modal dialog for Sign In and Sign Up."""
    st.caption(
        "Accounts are stored securely on this device in `runs/local_cdss.db` using PBKDF2 password hashing."
    )
    render_auth_forms(ClinicalHistoryStore(), default_mode=default_mode, key_prefix="dialog")


def render_sidebar_account_widget() -> None:
    """Render active clinician profile or Sign In / Sign Up actions in sidebar."""
    active_user = st.session_state.get("auth_username")
    if active_user:
        full_name = st.session_state.get("auth_full_name", active_user)
        role = st.session_state.get("auth_role", "Clinician")
        initials = "".join(part[0].upper() for part in str(full_name).split()[:2]) or active_user[:2].upper()
        try:
            saved_cnt = ClinicalHistoryStore().count_assessments(owner_username=active_user)
        except Exception:
            saved_cnt = 0

        full_name_safe = html.escape(str(full_name))
        user_safe = html.escape(str(active_user))
        role_safe = html.escape(str(role))
        initials_safe = html.escape(str(initials))

        st.sidebar.markdown(
            f"""
            <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(52, 211, 153, 0.35); border-radius: 11px; padding: 0.68rem 0.78rem; margin-bottom: 0.45rem;">
                <div style="display:flex; align-items:center; gap:0.6rem;">
                    <div style="width:32px; height:32px; border-radius:50%; background:#059669; color:#ffffff; font-weight:800; font-size:0.78rem; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                        {initials_safe}
                    </div>
                    <div style="min-width:0;">
                        <div style="font-size:0.84rem; font-weight:700; color:#ffffff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{full_name_safe}</div>
                        <div style="font-size:0.71rem; color:#a7f3d0;">@{user_safe} · {role_safe}</div>
                    </div>
                </div>
                <div style="font-size:0.71rem; color:#cbd5e1; margin-top:0.42rem;">
                    Saved Assessments: <b style="color:#ffffff;">{saved_cnt}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.sidebar.button("🚪 Sign Out", key="sb_sign_out_btn", use_container_width=True):
            sign_out_session()
            st.rerun()
    else:
        st.sidebar.markdown(
            """
            <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(148,163,184,0.20); border-radius: 10px; padding: 0.58rem 0.75rem; margin-bottom: 0.42rem;">
                <div style="font-size:0.76rem; font-weight:700; color:#e2e8f0;">Guest Session</div>
                <div style="font-size:0.70rem; color:#94a3b8; margin-top:0.12rem;">Sign in or register to save &amp; track your patient history.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        b1, b2 = st.sidebar.columns(2)
        with b1:
            if st.button("🔑 Sign In", key="sb_signin_btn", use_container_width=True):
                open_auth_dialog("signin")
        with b2:
            if st.button("📝 Sign Up", key="sb_signup_btn", type="primary", use_container_width=True):
                open_auth_dialog("signup")
