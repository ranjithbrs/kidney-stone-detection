"""NEFROAI-X FastAPI Backend Service.

Provides REST endpoints for:
- PBKDF2 + Signed Bearer Token Authentication (/api/auth/signup, /api/auth/signin, /api/auth/me)
- Unified CKD Screening, KDIGO Staging, & Longitudinal Progression (/api/assess, /api/presets)
- Live TreeSHAP, Live LIME, Concordance & Counterfactual Recourse (/api/explain)
- Batch CSV Screening, Schema Validation & PSI/Mahalanobis Drift (/api/batch-screen)
- 4-Family Stacking Benchmark, Calibration & CV Feature Stability (/api/performance)
- Cloud PostgreSQL / SQLite Scoped Patient Vault & SHA-256 Verification (/api/history*, /api/verify-attestation)
- Multi-format Medical Report Export (/api/reports/export)
- Production SPA serving for built React frontend (frontend/dist)
"""

from __future__ import annotations

import dataclasses
import functools
import io
import json
import os
import re
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import pandas as pd
from pydantic import BaseModel, Field

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
for p in (SRC_DIR, ROOT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(os.path.join(ROOT_DIR, ".env"), override=False)

# Register unpickling aliases for production clinical_pipeline.joblib
import src.pipeline as _pipe_mod
import src.preprocessing as _prep_mod

sys.modules.setdefault("pipeline", _pipe_mod)
sys.modules.setdefault("preprocessing", _prep_mod)

from src.clinical.assessment_contracts import (
    Demographics,
    Engine1Result,
    Engine1ScreeningInput,
    Engine2Result,
    Engine2SeverityInput,
    Engine3ProgressionInput,
    Engine3Result,
    PatientAssessmentRequest,
    ProvenanceSource,
    UnifiedAssessmentResponse,
)
from src.clinical.attestation import PROTECTED_MODEL_SHA256, verify_assessment_attestation
from src.clinical.batch_screening import (
    MAX_BATCH_FILE_BYTES,
    MAX_BATCH_ROWS,
    get_sample_batch_csv,
    run_batch_clinical_screening,
)
from src.clinical.conformal_calibrator import (
    get_calibrated_conformal_result,
    get_calibrated_mondrian_result,
)
from src.clinical.kfre_calculator import KFRECalibrationProfile, KFREInput
from src.clinical.patient_store import ClinicalHistoryStore
from src.clinical.progression_features import ClinicalObservation, LongitudinalPatientRecord
from src.clinical.stacking_ensemble import get_stacking_ensemble
from src.clinical.xai_live import (
    compute_live_lime,
    compute_live_treeshap,
    compute_xai_concordance,
    generate_clinical_counterfactuals,
)
from src.engines.unified_assessment_engine import UnifiedAssessmentEngine
from src.feature_selection import FeatureSelectionPipeline
from src.ui.components.report_export import (
    generate_csv_export,
    generate_pdf_report,
    generate_text_report,
)

# Ephemeral runtime fallback if NEFROAI_JWT_SECRET env var isn't supplied locally (never static hardcoded)
_RUNTIME_SECRET = os.getenv("NEFROAI_JWT_SECRET") or secrets.token_urlsafe(32)
TOKEN_TTL_SECONDS = int(os.getenv("NEFROAI_TOKEN_TTL_SECONDS", "86400"))


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_RUNTIME_SECRET, salt="nefroai-x-auth-v1")


def _create_access_token(user: Dict[str, Any]) -> str:
    payload = {
        "sub": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "email": user.get("email", ""),
    }
    return _get_serializer().dumps(payload)


def _decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return _get_serializer().loads(token, max_age=TOKEN_TTL_SECONDS)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc


@functools.lru_cache(maxsize=1)
def get_store() -> ClinicalHistoryStore:
    return ClinicalHistoryStore()


@functools.lru_cache(maxsize=1)
def get_engine() -> UnifiedAssessmentEngine:
    return UnifiedAssessmentEngine()


@functools.lru_cache(maxsize=1)
def get_cv_stability_cached() -> Dict[str, Any]:
    return FeatureSelectionPipeline(random_state=42).evaluate_cv_selection_stability(top_k=10, n_splits=5)


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def get_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[Dict[str, Any]]:
    tok = _extract_bearer_token(authorization)
    if not tok:
        return None
    try:
        return _get_serializer().loads(tok, max_age=TOKEN_TTL_SECONDS)
    except Exception:
        return None


def require_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    tok = _extract_bearer_token(authorization)
    if not tok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Sign in to access protected clinical history.",
        )
    return _decode_access_token(tok)


# ---------------------------------------------------------------------------
# Pydantic Request Schemas
# ---------------------------------------------------------------------------

class SignUpRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(default="Clinical User", min_length=1, max_length=120)
    role: str = Field(default="Clinician", max_length=60)
    email: str = Field(default="", max_length=160)


class SignInRequest(BaseModel):
    username_or_email: str = Field(..., min_length=1, max_length=160)
    password: str = Field(..., min_length=1, max_length=128)


class VisitPayload(BaseModel):
    date: str
    scr: float
    uacr: Optional[float] = None
    sbp: Optional[float] = None


class AssessRequest(BaseModel):
    patient_id: str = Field(default="PT-CLINICAL-001", max_length=80)
    age: float = Field(default=60.0, ge=1.0, le=120.0)
    sex: Literal["male", "female", "M", "F"] = "male"
    biomarkers: Dict[str, Any] = Field(default_factory=dict)
    serum_creatinine: Optional[float] = None
    serum_creatinine_unit: str = "mg/dL"
    uacr: Optional[float] = None
    uacr_unit: str = "mg/g"
    observation_date_scr: Optional[str] = None
    observation_date_uacr: Optional[str] = None
    kfre_calibration: str = KFRECalibrationProfile.NON_NORTH_AMERICA.value
    visits: List[VisitPayload] = Field(default_factory=list)
    requested_engines: List[str] = Field(default_factory=lambda: ["engine1", "engine2", "engine3"])
    is_synthetic_demonstration: bool = False
    auto_save: bool = True


class ExplainRequest(BaseModel):
    biomarkers: Dict[str, Any]
    uacr_mg_g: Optional[float] = None
    target_max_risk: float = Field(default=0.20, ge=0.05, le=0.50)
    max_changes: int = Field(default=2, ge=1, le=3)


class ExportRequest(BaseModel):
    format: Literal["pdf", "csv", "json", "txt"] = "pdf"
    response: Dict[str, Any]
    visits: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# FastAPI App Setup & CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="NEFROAI-X Cloud Clinical Decision Support API",
    description="Explainable CKD Screening, KDIGO Staging, Longitudinal Progression & Safety-Max API.",
    version="1.0.0",
)

_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:8000"
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    store = get_store()
    eng = get_engine()
    stack = get_stacking_ensemble()
    return {
        "status": "ok",
        "service": "nefroai-x-api",
        "storage_backend": store.storage_backend,
        "cloud_postgres_connected": store.storage_backend == "postgresql",
        "pipeline_loaded": eng.get_pipeline() is not None,
        "protected_model_sha256": PROTECTED_MODEL_SHA256,
        "xgboost_active": bool(stack.evaluation_report.get("xgboost_active")),
        "survival_ml_status": "DEFERRED_PENDING_APPROVED_COHORT",
    }


@app.post("/api/auth/signup")
def auth_signup(body: SignUpRequest) -> Dict[str, Any]:
    store = get_store()
    ok, msg = store.register_user(
        username=body.username,
        password=body.password,
        full_name=body.full_name,
        role=body.role,
        email=body.email,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    user = store.authenticate_user(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=500, detail="Registered user could not be loaded.")
    token = _create_access_token(user)
    return {
        "message": msg,
        "access_token": token,
        "token_type": "bearer",
        "user": {**user, "saved_count": store.count_assessments(user["username"])},
        "storage_backend": store.storage_backend,
    }


@app.post("/api/auth/signin")
def auth_signin(body: SignInRequest) -> Dict[str, Any]:
    store = get_store()
    user = store.authenticate_user(body.username_or_email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
        )
    token = _create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {**user, "saved_count": store.count_assessments(user["username"])},
        "storage_backend": store.storage_backend,
    }


@app.get("/api/auth/me")
def auth_me(user_claims: Dict[str, Any] = Depends(require_user)) -> Dict[str, Any]:
    store = get_store()
    uname = user_claims["sub"]
    return {
        "user": {
            "username": uname,
            "full_name": user_claims.get("full_name", uname),
            "role": user_claims.get("role", "Clinician"),
            "email": user_claims.get("email", ""),
            "saved_count": store.count_assessments(uname),
        },
        "storage_backend": store.storage_backend,
    }


@app.get("/api/presets")
def get_clinical_presets() -> Dict[str, Any]:
    today = date.today()
    return {
        "presets": {
            "healthy": {
                "label": "🟢 Healthy Cohort",
                "patient_id": "PT-HEALTHY-DEMO",
                "age": 38.0,
                "sex": "female",
                "biomarkers": {
                    "hemo": 14.5, "sg": 1.020, "pcv": 44.0, "sc": 0.85, "rc": 5.1,
                    "al": 0, "bu": 28.0, "bgr": 95.0, "htn": "no", "dm": "no",
                },
                "serum_creatinine": 0.85,
                "serum_creatinine_unit": "mg/dL",
                "uacr": 12.0,
                "uacr_unit": "mg/g",
                "visits": [
                    {"date": (today - timedelta(days=360)).isoformat(), "scr": 0.82, "uacr": 10.0, "sbp": 118.0},
                    {"date": (today - timedelta(days=180)).isoformat(), "scr": 0.84, "uacr": 12.0, "sbp": 120.0},
                    {"date": today.isoformat(), "scr": 0.85, "uacr": 12.0, "sbp": 118.0},
                ],
            },
            "high_risk_ckd": {
                "label": "🔴 High-Risk CKD",
                "patient_id": "PT-HIGH-RISK-CKD",
                "age": 64.0,
                "sex": "male",
                "biomarkers": {
                    "hemo": 9.8, "sg": 1.010, "pcv": 30.0, "sc": 2.4, "rc": 3.3,
                    "al": 3, "bu": 72.0, "bgr": 185.0, "htn": "yes", "dm": "yes",
                },
                "serum_creatinine": 2.4,
                "serum_creatinine_unit": "mg/dL",
                "uacr": 380.0,
                "uacr_unit": "mg/g",
                "visits": [
                    {"date": (today - timedelta(days=360)).isoformat(), "scr": 1.9, "uacr": 220.0, "sbp": 142.0},
                    {"date": (today - timedelta(days=180)).isoformat(), "scr": 2.1, "uacr": 310.0, "sbp": 148.0},
                    {"date": today.isoformat(), "scr": 2.4, "uacr": 380.0, "sbp": 152.0},
                ],
            },
            "discordant_false_assurance": {
                "label": "⚠️ Discordant (False Assurance)",
                "patient_id": "PT-DISCORDANT-001",
                "age": 48.0,
                "sex": "female",
                "biomarkers": {
                    "hemo": 14.5, "sg": 1.020, "pcv": 43.0, "sc": 1.4, "rc": 4.9,
                    "al": 0, "bu": 24.0, "bgr": 95.0, "htn": "no", "dm": "no",
                },
                "serum_creatinine": 1.4,
                "serum_creatinine_unit": "mg/dL",
                "uacr": 420.0,
                "uacr_unit": "mg/g",
                "visits": [],
            },
            "si_units_healthy": {
                "label": "🌍 EU/UK SI Units Healthy",
                "patient_id": "PT-UK-SI-001",
                "age": 44.0,
                "sex": "male",
                "biomarkers": {
                    "hemo": 150.0, "sg": 1.025, "pcv": 45.0, "sc": 88.42, "rc": 5.0,
                    "al": 0, "bu": 28.0, "bgr": 5.2, "htn": "no", "dm": "no",
                },
                "serum_creatinine": 88.42,
                "serum_creatinine_unit": "µmol/L",
                "uacr": 1.2,
                "uacr_unit": "mg/mmol",
                "visits": [],
            },
        }
    }


def _parse_iso_dt(date_str: Optional[str]) -> datetime:
    if not date_str:
        return datetime.now(timezone.utc)
    d = date.fromisoformat(str(date_str)[:10])
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


@app.post("/api/assess")
def assess_patient(
    body: AssessRequest,
    user_claims: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> Dict[str, Any]:
    engine = get_engine()
    prov = (
        ProvenanceSource.SYNTHETIC_DEMONSTRATION.value
        if body.is_synthetic_demonstration
        else ProvenanceSource.CLINICAL_EHR.value
    )

    biomarkers = dict(body.biomarkers)
    biomarkers.setdefault("age", body.age)

    dt_scr = _parse_iso_dt(body.observation_date_scr)
    dt_uacr = _parse_iso_dt(body.observation_date_uacr)

    e1_input = Engine1ScreeningInput(
        biomarkers=biomarkers,
        observation_date=dt_scr,
        provenance=prov,
    )

    scr_for_e2 = body.serum_creatinine if body.serum_creatinine is not None else biomarkers.get("sc")
    e2_input = None
    if scr_for_e2 is not None or body.uacr is not None:
        try:
            scr_num = float(scr_for_e2) if scr_for_e2 is not None else None
        except (TypeError, ValueError):
            scr_num = None
        e2_input = Engine2SeverityInput(
            serum_creatinine=scr_num,
            serum_creatinine_unit=body.serum_creatinine_unit,
            uacr=body.uacr,
            uacr_unit=body.uacr_unit,
            age=body.age,
            sex=body.sex,
            observation_date_scr=dt_scr,
            observation_date_uacr=dt_uacr,
            provenance=prov,
        )

    e3_input = None
    if "engine3" in body.requested_engines:
        if body.visits:
            obs = []
            for v in sorted(body.visits, key=lambda item: item.date):
                obs.append(
                    ClinicalObservation(
                        timestamp=_parse_iso_dt(v.date),
                        serum_creatinine=float(v.scr),
                        uacr=float(v.uacr) if v.uacr is not None else None,
                        systolic_bp=float(v.sbp) if v.sbp is not None else None,
                    )
                )
            rec = LongitudinalPatientRecord(
                patient_id=body.patient_id,
                age_baseline=float(body.age),
                sex=str(body.sex),
                diabetes_history=True if str(biomarkers.get("dm", "")).lower() == "yes" else (False if str(biomarkers.get("dm", "")).lower() == "no" else None),
                hypertension_history=True if str(biomarkers.get("htn", "")).lower() == "yes" else (False if str(biomarkers.get("htn", "")).lower() == "no" else None),
                observations=obs,
                is_synthetic=body.is_synthetic_demonstration,
                provenance=prov,
            )
            e3_input = Engine3ProgressionInput(
                longitudinal_record=rec,
                landmark_time=obs[-1].timestamp,
                kfre_calibration=body.kfre_calibration,
                provenance=prov,
            )
        elif e2_input is not None:
            e3_input = Engine3ProgressionInput(
                kfre_input=KFREInput(
                    age=body.age,
                    sex=body.sex,
                    egfr=None,
                    uacr=body.uacr,
                ),
                kfre_calibration=body.kfre_calibration,
                provenance=prov,
            )

    req = PatientAssessmentRequest(
        patient_id=body.patient_id,
        demographics=Demographics(age=body.age, sex=body.sex),
        engine1_input=e1_input if "engine1" in body.requested_engines else None,
        engine2_input=e2_input if "engine2" in body.requested_engines else None,
        engine3_input=e3_input if "engine3" in body.requested_engines else None,
        requested_engines=body.requested_engines,
        provenance=prov,
    )

    resp = engine.assess_patient(req)
    resp_dict = resp.to_dict()

    saved_row_id: Optional[int] = None
    if user_claims and body.auto_save:
        store = get_store()
        sbp_val = body.visits[-1].sbp if body.visits else None
        saved_row_id = store.save_assessment(
            resp,
            owner_username=user_claims["sub"],
            observation_date=dt_scr.date().isoformat(),
            systolic_bp=sbp_val,
        )

    return {
        "assessment": resp_dict,
        "saved_to_vault": saved_row_id is not None,
        "saved_row_id": saved_row_id,
        "storage_backend": get_store().storage_backend,
    }


@app.post("/api/explain")
def explain_patient(body: ExplainRequest) -> Dict[str, Any]:
    pipeline_obj = get_engine().get_pipeline()
    if pipeline_obj is None:
        raise HTTPException(status_code=503, detail="Production pipeline not loaded.")

    shap_res = compute_live_treeshap(pipeline_obj, body.biomarkers)
    lime_res = compute_live_lime(pipeline_obj, body.biomarkers)
    conc_res = compute_xai_concordance(shap_res, lime_res, uacr_mg_g=body.uacr_mg_g)
    cf_res = generate_clinical_counterfactuals(
        pipeline_obj,
        body.biomarkers,
        target_max_risk=body.target_max_risk,
        max_changes=body.max_changes,
    )

    return {
        "treeshap": shap_res.to_dict() if shap_res else None,
        "lime": lime_res.to_dict() if lime_res else None,
        "concordance": conc_res.to_dict() if conc_res else None,
        "counterfactual": cf_res.to_dict() if cf_res else None,
    }


@app.get("/api/sample-batch-csv")
def sample_batch_csv() -> Dict[str, str]:
    return {"csv": get_sample_batch_csv()}


@app.post("/api/batch-screen")
async def batch_screen_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_BATCH_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB security upload limit.")

    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), nrows=MAX_BATCH_ROWS + 1)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV syntax: {exc}") from exc

    if len(df) > MAX_BATCH_ROWS:
        raise HTTPException(status_code=400, detail=f"Row limit exceeded (max {MAX_BATCH_ROWS} rows).")

    pipeline_obj = get_engine().get_pipeline()
    summary = run_batch_clinical_screening(df, pipeline=pipeline_obj, max_rows=MAX_BATCH_ROWS)
    if not summary.schema_valid:
        return {
            "schema_valid": False,
            "schema_message": summary.schema_message,
            "total_rows": summary.total_rows,
        }

    records = json.loads(summary.results_df.to_json(orient="records"))
    drift_dict = summary.drift_report.to_dict() if hasattr(summary.drift_report, "to_dict") else summary.drift_report
    return {
        "schema_valid": True,
        "schema_message": summary.schema_message,
        "total_rows": summary.total_rows,
        "predictions_available": summary.predictions_available,
        "incomplete_estimates": summary.incomplete_estimates,
        "abstained_rows": summary.abstained_rows,
        "conformal_abstentions": summary.conformal_abstentions,
        "high_or_critical_risk": summary.high_or_critical_risk,
        "mean_cri": summary.mean_cri,
        "conformal_quantile": summary.conformal_quantile,
        "drift_report": drift_dict,
        "rows": records,
        "sanitized_csv": summary.to_sanitized_csv(),
    }


@app.get("/api/performance")
def get_model_performance() -> Dict[str, Any]:
    stack = get_stacking_ensemble()
    cv_stab = get_cv_stability_cached()
    split_cal = get_calibrated_conformal_result()
    mondrian_cal = get_calibrated_mondrian_result()

    return {
        "stacking_report": stack.evaluation_report,
        "feature_selection_stability": cv_stab,
        "conformal_split": split_cal.to_dict(),
        "conformal_mondrian": mondrian_cal.to_dict(),
    }


@app.get("/api/history")
def list_history(
    patient_id: Optional[str] = None,
    limit: int = 100,
    user_claims: Dict[str, Any] = Depends(require_user),
) -> Dict[str, Any]:
    store = get_store()
    rows = store.list_assessments(
        patient_id=patient_id,
        owner_username=user_claims["sub"],
        limit=min(max(limit, 1), 500),
    )
    return {
        "owner_username": user_claims["sub"],
        "storage_backend": store.storage_backend,
        "records": rows,
    }


@app.get("/api/history/{assessment_id}")
def get_history_record(
    assessment_id: str,
    user_claims: Dict[str, Any] = Depends(require_user),
) -> Dict[str, Any]:
    store = get_store()
    owner_rows = store.list_assessments(owner_username=user_claims["sub"], limit=500)
    if not any(r.get("assessment_id") == assessment_id for r in owner_rows):
        raise HTTPException(status_code=404, detail="Assessment record not found for this account.")
    payload = store.get_assessment_payload(assessment_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Assessment payload not found.")
    v_ok, exp_sha, comp_sha = verify_assessment_attestation(payload)
    return {
        "payload": payload,
        "attestation_verified": v_ok,
        "expected_sha256": exp_sha,
        "recomputed_sha256": comp_sha,
    }


@app.get("/api/history/visits/{patient_id}")
def get_patient_visits(
    patient_id: str,
    user_claims: Dict[str, Any] = Depends(require_user),
) -> Dict[str, Any]:
    store = get_store()
    visits = store.load_patient_visits_for_engine3(patient_id=patient_id, owner_username=user_claims["sub"])
    serialized = [
        {
            "date": v["date"].isoformat() if hasattr(v["date"], "isoformat") else str(v["date"]),
            "scr": v["scr"],
            "uacr": v["uacr"],
            "sbp": v["sbp"],
        }
        for v in visits
    ]
    return {"patient_id": patient_id, "visits": serialized}


@app.post("/api/verify-attestation")
def verify_attestation_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    verified, expected_sha, recomputed_sha = verify_assessment_attestation(payload)
    return {
        "verified": verified,
        "expected_sha256": expected_sha,
        "recomputed_sha256": recomputed_sha,
    }


def _dc_from_dict(cls: Any, data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid_fields}
    return cls(**filtered)


def _rehydrate_response(raw: Dict[str, Any]) -> UnifiedAssessmentResponse:
    valid_top = {f.name for f in dataclasses.fields(UnifiedAssessmentResponse)}
    filtered = {
        k: v
        for k, v in raw.items()
        if k in valid_top and k not in ("engine1_result", "engine2_result", "engine3_result")
    }
    filtered.setdefault("assessment_id", "EXPORT")
    filtered.setdefault("patient_id", "UNKNOWN")
    filtered.setdefault("assessment_timestamp", datetime.now(timezone.utc).isoformat())
    return UnifiedAssessmentResponse(
        engine1_result=_dc_from_dict(Engine1Result, raw.get("engine1_result")),
        engine2_result=_dc_from_dict(Engine2Result, raw.get("engine2_result")),
        engine3_result=_dc_from_dict(Engine3Result, raw.get("engine3_result")),
        **filtered,
    )


@app.post("/api/reports/export")
def export_report(body: ExportRequest) -> Response:
    resp_obj = _rehydrate_response(body.response)
    safe_pid = re.sub(r"[^A-Za-z0-9._-]", "_", str(resp_obj.patient_id or "PATIENT"))
    safe_aid = re.sub(r"[^A-Za-z0-9._-]", "_", str((resp_obj.assessment_id or "EXPORT")[:8]))
    base_name = f"nefroai_{safe_pid}_{safe_aid}"

    if body.format == "txt":
        return Response(
            content=generate_text_report(resp_obj),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.txt"'},
        )
    if body.format == "csv":
        return Response(
            content=generate_csv_export(resp_obj),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.csv"'},
        )
    if body.format == "json":
        return Response(
            content=json.dumps(body.response, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.json"'},
        )

    obs_parsed = []
    for v in body.visits:
        try:
            d_obj = date.fromisoformat(str(v.get("date"))[:10])
            obs_parsed.append({"date": d_obj, "scr": float(v["scr"]), "uacr": v.get("uacr"), "sbp": v.get("sbp")})
        except Exception:
            continue
    pdf_bytes = generate_pdf_report(resp_obj, observations=obs_parsed)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{base_name}.pdf"'},
    )


# ---------------------------------------------------------------------------
# Serve Built React SPA (frontend/dist) in Production / Single-Host Cloud
# ---------------------------------------------------------------------------

FRONTEND_DIST = os.path.join(ROOT_DIR, "frontend", "dist")
if os.path.isdir(FRONTEND_DIST) and os.path.isfile(os.path.join(FRONTEND_DIST, "index.html")):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

    @app.get("/{full_path:path}")
    def serve_react_spa(full_path: str) -> Response:
        if full_path.startswith("api"):
            return JSONResponse({"detail": "API route not found"}, status_code=404)
        dist_real = os.path.realpath(FRONTEND_DIST)
        candidate_real = os.path.realpath(os.path.join(FRONTEND_DIST, full_path))
        if (
            full_path
            and candidate_real.startswith(dist_real + os.sep)
            and os.path.isfile(candidate_real)
        ):
            return FileResponse(candidate_real)
        return FileResponse(os.path.join(dist_real, "index.html"))
