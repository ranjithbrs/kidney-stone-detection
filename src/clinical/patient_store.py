"""Cloud PostgreSQL / Supabase & Local SQLite Clinician History Store.

Supports:
- Cloud PostgreSQL / Supabase via `DATABASE_URL` or `SUPABASE_DB_URL`
  (SQLAlchemy pooled engine + psycopg3, connection pre-ping, PgBouncer-safe).
- Automatic local SQLite fallback ONLY when no cloud `DATABASE_URL` is set
  or when an explicit `db_path` is passed (e.g., isolated unit tests).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool
from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_DB_PATH = os.path.join("runs", "local_cdss.db")


def _normalize_db_url(raw_url: str) -> str:
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _iso_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return str(val)


class ClinicalHistoryStore:
    """Dual-backend (Cloud PostgreSQL / SQLite fallback) auth & assessment vault."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        database_url: Optional[str] = None,
    ) -> None:
        env_url = (
            database_url
            or (None if db_path is not None else (os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")))
        )
        if env_url and str(env_url).strip() and not str(env_url).strip().startswith("sqlite"):
            self.database_url = _normalize_db_url(str(env_url))
            self.db_path = None
            self.storage_backend = "postgresql"
            connect_args: Dict[str, Any] = {}
            # PgBouncer transaction poolers (e.g. Supabase port 6543) disallow prepared statements
            if ":6543/" in self.database_url or "pgbouncer=true" in self.database_url.lower():
                connect_args["prepare_threshold"] = None
            self.engine: Engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args=connect_args,
            )
        else:
            effective_path = db_path or DEFAULT_DB_PATH
            parent = os.path.dirname(os.path.abspath(effective_path))
            os.makedirs(parent, exist_ok=True)
            self.db_path = effective_path
            self.database_url = f"sqlite:///{os.path.abspath(effective_path)}"
            self.storage_backend = "sqlite"
            self.engine = create_engine(self.database_url, poolclass=NullPool)

        self._init_schema()

    def close(self) -> None:
        """Dispose underlying SQLAlchemy engine cleanly."""
        self.engine.dispose()

    def _init_schema(self) -> None:
        with self.engine.begin() as conn:
            if self.storage_backend == "postgresql":
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS public.users (
                        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        username text UNIQUE NOT NULL,
                        full_name text NOT NULL,
                        email text NOT NULL DEFAULT '',
                        role text NOT NULL DEFAULT 'Clinician',
                        password_hash text NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS users_email_lower_idx
                        ON public.users (lower(email)) WHERE email <> ''
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS public.assessments (
                        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        assessment_id text UNIQUE NOT NULL,
                        patient_id text NOT NULL,
                        owner_username text NOT NULL,
                        recorded_at timestamptz NOT NULL DEFAULT now(),
                        observation_date date,
                        serum_creatinine double precision,
                        egfr double precision,
                        uacr double precision,
                        systolic_bp double precision,
                        e1_risk_probability double precision,
                        e1_diagnosis text,
                        kdigo_stage text,
                        arbitration_tier text,
                        attestation_sha256 text,
                        payload_json jsonb NOT NULL
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS assessments_owner_patient_idx
                        ON public.assessments (owner_username, patient_id, observation_date ASC, recorded_at ASC)
                """))
            else:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        full_name TEXT NOT NULL,
                        email TEXT DEFAULT '',
                        role TEXT NOT NULL DEFAULT 'Clinician',
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """))
                cols = {r[1] for r in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
                if "email" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''"))

                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS assessments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assessment_id TEXT UNIQUE NOT NULL,
                        patient_id TEXT NOT NULL,
                        owner_username TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        observation_date TEXT,
                        serum_creatinine REAL,
                        egfr REAL,
                        uacr REAL,
                        systolic_bp REAL,
                        e1_risk_probability REAL,
                        e1_diagnosis TEXT,
                        kdigo_stage TEXT,
                        arbitration_tier TEXT,
                        attestation_sha256 TEXT,
                        payload_json TEXT NOT NULL
                    )
                """))

    def register_user(
        self,
        username: str,
        password: str,
        full_name: str = "Clinical Researcher",
        role: str = "Clinician",
        email: str = "",
    ) -> Tuple[bool, str]:
        """Register a new account using PBKDF2 password hashing."""
        uname = (username or "").strip()
        clean_email = (email or "").strip().lower()
        if len(uname) < 3:
            return False, "Username must be at least 3 characters."
        if " " in uname:
            return False, "Username cannot contain spaces."
        if len(password or "") < 6:
            return False, "Password must be at least 6 characters."
        if clean_email and ("@" not in clean_email or "." not in clean_email.split("@")[-1]):
            return False, "Please enter a valid email address (or leave it blank)."

        pw_hash = generate_password_hash(password)
        now_dt = datetime.now(timezone.utc)
        now_val: Any = now_dt if self.storage_backend == "postgresql" else now_dt.isoformat()

        try:
            with self.engine.begin() as conn:
                if clean_email:
                    existing_mail = conn.execute(
                        text("SELECT id FROM users WHERE LOWER(email) = :email"),
                        {"email": clean_email},
                    ).fetchone()
                    if existing_mail is not None:
                        return False, f"Email '{clean_email}' is already registered."
                conn.execute(
                    text(
                        "INSERT INTO users (username, full_name, email, role, password_hash, created_at) "
                        "VALUES (:username, :full_name, :email, :role, :password_hash, :created_at)"
                    ),
                    {
                        "username": uname,
                        "full_name": full_name.strip() or uname,
                        "email": clean_email,
                        "role": role,
                        "password_hash": pw_hash,
                        "created_at": now_val,
                    },
                )
            return True, f"Account '{uname}' registered securely."
        except IntegrityError:
            return False, f"Username '{uname}' already exists."

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate username (or email) and password against stored PBKDF2 hash."""
        ident = (username or "").strip()
        if not ident or not password:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, username, full_name, email, role, password_hash, created_at "
                    "FROM users WHERE LOWER(username) = LOWER(:ident) "
                    "OR (email <> '' AND LOWER(email) = LOWER(:ident))"
                ),
                {"ident": ident},
            ).mappings().fetchone()
        if row is None:
            return None
        if not check_password_hash(row["password_hash"], password):
            return None
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "full_name": row["full_name"],
            "email": row["email"] or "",
            "role": row["role"],
            "created_at": _iso_str(row["created_at"]),
        }

    def count_assessments(self, owner_username: Optional[str] = None) -> int:
        """Count stored assessments optionally scoped by owner_username."""
        with self.engine.connect() as conn:
            if owner_username:
                row = conn.execute(
                    text("SELECT COUNT(*) AS cnt FROM assessments WHERE owner_username = :owner"),
                    {"owner": owner_username},
                ).mappings().fetchone()
            else:
                row = conn.execute(text("SELECT COUNT(*) AS cnt FROM assessments")).mappings().fetchone()
        return int(row["cnt"]) if row else 0

    def save_assessment(
        self,
        response: Any,
        owner_username: str = "guest_researcher",
        observation_date: Optional[str] = None,
        systolic_bp: Optional[float] = None,
    ) -> int:
        """Persist a UnifiedAssessmentResponse snapshot using cross-DB upsert."""
        resp_dict = response.to_dict() if hasattr(response, "to_dict") else dict(response)
        e1 = resp_dict.get("engine1_result") or {}
        e2 = resp_dict.get("engine2_result") or {}
        san_e1 = e1.get("sanitized_inputs") or {}

        scr = san_e1.get("sc")
        if scr is None and e2.get("egfr") is not None:
            scr = resp_dict.get("provenance", {}).get("metadata", {}).get("serum_creatinine")

        obs_dt = observation_date or e2.get("observation_date_scr") or resp_dict.get("assessment_timestamp", "")[:10]
        if hasattr(obs_dt, "isoformat"):
            obs_dt = obs_dt.isoformat()[:10]
        obs_dt_str = str(obs_dt)[:10] if obs_dt else datetime.now(timezone.utc).date().isoformat()
        obs_dt_param: Any = date.fromisoformat(obs_dt_str) if self.storage_backend == "postgresql" else obs_dt_str

        rec_ts = resp_dict.get("assessment_timestamp") or datetime.now(timezone.utc).isoformat()
        att_sha = (resp_dict.get("provenance") or {}).get("attestation_sha256")
        arb_tier = (resp_dict.get("overall_completeness") or {}).get("arbitration_tier")
        payload_expr = "CAST(:payload_json AS jsonb)" if self.storage_backend == "postgresql" else ":payload_json"

        sql = text(
            f"""
            INSERT INTO assessments (
                assessment_id, patient_id, owner_username, recorded_at, observation_date,
                serum_creatinine, egfr, uacr, systolic_bp, e1_risk_probability,
                e1_diagnosis, kdigo_stage, arbitration_tier, attestation_sha256, payload_json
            ) VALUES (
                :assessment_id, :patient_id, :owner_username, :recorded_at, :observation_date,
                :serum_creatinine, :egfr, :uacr, :systolic_bp, :e1_risk_probability,
                :e1_diagnosis, :kdigo_stage, :arbitration_tier, :attestation_sha256, {payload_expr}
            )
            ON CONFLICT (assessment_id) DO UPDATE SET
                patient_id = EXCLUDED.patient_id,
                owner_username = EXCLUDED.owner_username,
                recorded_at = EXCLUDED.recorded_at,
                observation_date = EXCLUDED.observation_date,
                serum_creatinine = EXCLUDED.serum_creatinine,
                egfr = EXCLUDED.egfr,
                uacr = EXCLUDED.uacr,
                systolic_bp = EXCLUDED.systolic_bp,
                e1_risk_probability = EXCLUDED.e1_risk_probability,
                e1_diagnosis = EXCLUDED.e1_diagnosis,
                kdigo_stage = EXCLUDED.kdigo_stage,
                arbitration_tier = EXCLUDED.arbitration_tier,
                attestation_sha256 = EXCLUDED.attestation_sha256,
                payload_json = EXCLUDED.payload_json
            RETURNING id
            """
        )

        params = {
            "assessment_id": resp_dict["assessment_id"],
            "patient_id": resp_dict["patient_id"],
            "owner_username": owner_username or "guest_researcher",
            "recorded_at": rec_ts,
            "observation_date": obs_dt_param,
            "serum_creatinine": float(scr) if scr is not None else None,
            "egfr": float(e2["egfr"]) if e2.get("egfr") is not None else None,
            "uacr": float(e2["uacr"]) if e2.get("uacr") is not None else None,
            "systolic_bp": float(systolic_bp) if systolic_bp is not None else None,
            "e1_risk_probability": float(e1["risk_probability"]) if e1.get("risk_probability") is not None else None,
            "e1_diagnosis": e1.get("diagnosis"),
            "kdigo_stage": e2.get("cga_string"),
            "arbitration_tier": arb_tier,
            "attestation_sha256": att_sha,
            "payload_json": json.dumps(resp_dict, default=str),
        }

        with self.engine.begin() as conn:
            row = conn.execute(sql, params).fetchone()
            return int(row[0]) if row else 0

    def list_assessments(
        self,
        patient_id: Optional[str] = None,
        owner_username: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query stored assessment summaries scoped by optional patient_id or owner."""
        clauses: List[str] = []
        params: Dict[str, Any] = {"limit": int(limit)}
        if patient_id:
            clauses.append("patient_id = :patient_id")
            params["patient_id"] = patient_id.strip()
        if owner_username:
            clauses.append("owner_username = :owner_username")
            params["owner_username"] = owner_username.strip()

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = text(
            f"""
            SELECT assessment_id, patient_id, owner_username, recorded_at, observation_date,
                   serum_creatinine, egfr, uacr, systolic_bp, e1_risk_probability,
                   e1_diagnosis, kdigo_stage, arbitration_tier, attestation_sha256
            FROM assessments
            {where_sql}
            ORDER BY observation_date ASC, recorded_at ASC
            LIMIT :limit
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            item["recorded_at"] = _iso_str(item.get("recorded_at"))
            item["observation_date"] = _iso_str(item.get("observation_date"))
            results.append(item)
        return results

    def get_assessment_payload(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full serialized UnifiedAssessmentResponse JSON for a record."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT payload_json FROM assessments WHERE assessment_id = :aid"),
                {"aid": assessment_id},
            ).mappings().fetchone()
        if row is None:
            return None
        raw = row["payload_json"]
        return raw if isinstance(raw, dict) else json.loads(raw)

    def load_patient_visits_for_engine3(
        self,
        patient_id: str,
        owner_username: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return chronological visit dicts compatible with Engine 3 `e3_observations`."""
        rows = self.list_assessments(patient_id=patient_id, owner_username=owner_username, limit=200)
        visits: List[Dict[str, Any]] = []
        for r in rows:
            if r.get("serum_creatinine") is None:
                continue
            dt_str = str(r.get("observation_date") or r.get("recorded_at") or "")[:10]
            try:
                dt_obj = datetime.fromisoformat(dt_str).date()
            except Exception:
                continue
            visits.append({
                "date": dt_obj,
                "scr": float(r["serum_creatinine"]),
                "uacr": float(r["uacr"]) if r.get("uacr") is not None else None,
                "sbp": float(r["systolic_bp"]) if r.get("systolic_bp") is not None else None,
            })
        visits.sort(key=lambda v: v["date"])
        return visits
