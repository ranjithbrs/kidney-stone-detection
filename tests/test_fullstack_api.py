"""Automated REST API & Storage Tests for the FastAPI + Cloud/SQLite Full-Stack Service."""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import backend.main as backend_main
from src.clinical.patient_store import ClinicalHistoryStore, _normalize_db_url


@pytest.fixture()
def api_client(monkeypatch):
    """Provide a FastAPI TestClient wired to an isolated temporary SQLite store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_api_vault.db")
        isolated_store = ClinicalHistoryStore(db_path=db_file)
        monkeypatch.setattr(backend_main, "get_store", lambda: isolated_store)
        try:
            with TestClient(backend_main.app) as client:
                yield client, isolated_store
        finally:
            isolated_store.close()


def test_normalize_postgres_url_variants():
    assert _normalize_db_url("postgres://u:p@host:5432/db").startswith("postgresql+psycopg://")
    assert _normalize_db_url("postgresql://u:p@host:6543/db").startswith("postgresql+psycopg://")
    assert _normalize_db_url("  postgres://a@b/c ") == "postgresql+psycopg://a@b/c"


def test_health_and_presets(api_client):
    client, _ = api_client
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["pipeline_loaded"] is True
    assert body["survival_ml_status"] == "DEFERRED_PENDING_APPROVED_COHORT"
    assert len(body["protected_model_sha256"]) == 64

    p = client.get("/api/presets")
    assert p.status_code == 200
    presets = p.json()["presets"]
    for key in ("healthy", "high_risk_ckd", "discordant_false_assurance", "si_units_healthy"):
        assert key in presets
        assert "biomarkers" in presets[key]


def test_auth_signup_signin_me_and_history_isolation(api_client):
    client, _ = api_client

    # Unauthenticated access to protected history endpoints must be denied
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/history").status_code == 401

    pw_a = f"Clinician!{secrets.token_hex(6)}"
    pw_b = f"Clinician!{secrets.token_hex(6)}"

    # Sign up Clinician A (returns Bearer token directly)
    s_a = client.post(
        "/api/auth/signup",
        json={
            "username": "dr_alpha",
            "password": pw_a,
            "full_name": "Dr. Alpha Nephro",
            "role": "Nephrologist",
            "email": "alpha@nefroai.example",
        },
    )
    assert s_a.status_code == 200
    tok_a = s_a.json()["access_token"]
    assert s_a.json()["user"]["username"] == "dr_alpha"

    # Sign in via email works identically to username
    li_a = client.post(
        "/api/auth/signin",
        json={"username_or_email": "alpha@nefroai.example", "password": pw_a},
    )
    assert li_a.status_code == 200
    tok_a = li_a.json()["access_token"]

    me_a = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok_a}"})
    assert me_a.status_code == 200
    assert me_a.json()["user"]["username"] == "dr_alpha"

    # Sign up Clinician B
    s_b = client.post(
        "/api/auth/signup",
        json={
            "username": "dr_beta",
            "password": pw_b,
            "full_name": "Dr. Beta Physician",
            "role": "Physician",
            "email": "beta@nefroai.example",
        },
    )
    assert s_b.status_code == 200
    tok_b = s_b.json()["access_token"]

    # Run High-Risk CKD assessment authenticated as Clinician A -> auto-saved to DB
    presets = client.get("/api/presets").json()["presets"]
    high = presets["high_risk_ckd"]
    res_assess = client.post(
        "/api/assess",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={
            "patient_id": high["patient_id"],
            "age": high["age"],
            "sex": high["sex"],
            "biomarkers": high["biomarkers"],
            "serum_creatinine": high["serum_creatinine"],
            "serum_creatinine_unit": high["serum_creatinine_unit"],
            "uacr": high["uacr"],
            "uacr_unit": high["uacr_unit"],
            "visits": high["visits"],
            "auto_save": True,
        },
    )
    assert res_assess.status_code == 200
    assess_body = res_assess.json()
    assert assess_body["saved_to_vault"] is True
    assessment = assess_body["assessment"]
    aid = assessment["assessment_id"]
    assert assessment["engine1_result"]["diagnostic_class"] == 1
    assert assessment["engine1_result"]["risk_probability"] >= 0.70
    assert assessment["engine2_result"]["egfr"] is not None

    # Clinician A sees the saved record and verified SHA-256 payload
    hist_a = client.get("/api/history", headers={"Authorization": f"Bearer {tok_a}"})
    assert hist_a.status_code == 200
    assert len(hist_a.json()["records"]) == 1

    rec_a = client.get(f"/api/history/{aid}", headers={"Authorization": f"Bearer {tok_a}"})
    assert rec_a.status_code == 200
    assert rec_a.json()["attestation_verified"] is True

    visits_a = client.get(
        f"/api/history/visits/{high['patient_id']}",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert visits_a.status_code == 200
    assert len(visits_a.json()["visits"]) >= 1

    # BOLA/IDOR check: Clinician B must NOT see Clinician A's record or fetch it by ID
    hist_b = client.get("/api/history", headers={"Authorization": f"Bearer {tok_b}"})
    assert hist_b.status_code == 200
    assert len(hist_b.json()["records"]) == 0
    rec_b = client.get(f"/api/history/{aid}", headers={"Authorization": f"Bearer {tok_b}"})
    assert rec_b.status_code == 404


def test_healthy_assessment_attestation_tamper_and_exports(api_client):
    client, _ = api_client
    presets = client.get("/api/presets").json()["presets"]
    healthy = presets["healthy"]

    res = client.post(
        "/api/assess",
        json={
            "patient_id": healthy["patient_id"],
            "age": healthy["age"],
            "sex": healthy["sex"],
            "biomarkers": healthy["biomarkers"],
            "serum_creatinine": healthy["serum_creatinine"],
            "serum_creatinine_unit": healthy["serum_creatinine_unit"],
            "uacr": healthy["uacr"],
            "uacr_unit": healthy["uacr_unit"],
            "visits": healthy["visits"],
            "auto_save": False,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["saved_to_vault"] is False
    assessment = body["assessment"]
    assert assessment["engine1_result"]["diagnostic_class"] == 0
    assert assessment["engine1_result"]["risk_probability"] < 0.30

    # Attestation check passes intact, fails when tampered
    v_ok = client.post("/api/verify-attestation", json=assessment)
    assert v_ok.status_code == 200
    assert v_ok.json()["verified"] is True

    tampered = {**assessment, "engine1_result": {**assessment["engine1_result"], "risk_probability": 0.99}}
    v_bad = client.post("/api/verify-attestation", json=tampered)
    assert v_bad.status_code == 200
    assert v_bad.json()["verified"] is False

    # Report exports in PDF, CSV, JSON, TXT
    for fmt, expected_prefix in (("pdf", b"%PDF"), ("csv", b""), ("json", b"{"), ("txt", b"")):
        exp = client.post(
            "/api/reports/export",
            json={"format": fmt, "response": assessment, "visits": healthy["visits"]},
        )
        assert exp.status_code == 200
        assert len(exp.content) > 50
        if expected_prefix:
            assert exp.content.startswith(expected_prefix)


def test_explain_performance_and_batch_schema_guard(api_client):
    client, _ = api_client
    presets = client.get("/api/presets").json()["presets"]
    high = presets["high_risk_ckd"]

    exp = client.post(
        "/api/explain",
        json={
            "biomarkers": high["biomarkers"],
            "uacr_mg_g": high["uacr"],
            "target_max_risk": 0.25,
            "max_changes": 2,
        },
    )
    assert exp.status_code == 200
    exp_body = exp.json()
    assert exp_body["treeshap"] is not None
    assert len(exp_body["treeshap"]["top_drivers"]) >= 5
    assert exp_body["lime"] is not None
    assert exp_body["concordance"] is not None
    assert exp_body["counterfactual"] is not None

    perf = client.get("/api/performance")
    assert perf.status_code == 200
    perf_body = perf.json()
    assert len(perf_body["stacking_report"]["models"]) >= 5
    assert perf_body["feature_selection_stability"]["mean_pairwise_jaccard"] > 0.7
    assert "conformal_quantile" in perf_body["conformal_split"]
    assert "q_healthy" in perf_body["conformal_mondrian"]

    # Valid batch CSV succeeds
    sample_csv = client.get("/api/sample-batch-csv").json()["csv"].encode("utf-8")
    batch_ok = client.post(
        "/api/batch-screen",
        files={"file": ("cohort.csv", sample_csv, "text/csv")},
    )
    assert batch_ok.status_code == 200
    b_json = batch_ok.json()
    assert b_json["schema_valid"] is True
    assert b_json["total_rows"] >= 1
    assert "drift_report" in b_json

    # Incompatible kidney-stone CSV rejected cleanly by clinical schema guard
    stone_csv = b"gravity,ph,osmo,cond,urea,calc,target\n1.02,5.5,700,20,300,3.2,1\n"
    batch_reject = client.post(
        "/api/batch-screen",
        files={"file": ("kidney_stone.csv", stone_csv, "text/csv")},
    )
    assert batch_reject.status_code == 200
    assert batch_reject.json()["schema_valid"] is False

    # Non-CSV file rejected with 400
    bad_ext = client.post(
        "/api/batch-screen",
        files={"file": ("image.png", b"notcsv", "image/png")},
    )
    assert bad_ext.status_code == 400
