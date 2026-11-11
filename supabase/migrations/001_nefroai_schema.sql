-- NEFROAI-X Cloud PostgreSQL / Supabase Migration Schema
-- Follows Supabase Postgres Best Practices:
--   * bigint identity PKs, text strings, timestamptz timestamps, jsonb payloads
--   * Explicit indexes on owner_username, patient_id, and chronological dates
--   * Row-Level Security (RLS) enabled on exposed public schema tables

CREATE TABLE IF NOT EXISTS public.users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text UNIQUE NOT NULL,
    full_name text NOT NULL,
    email text NOT NULL DEFAULT '',
    role text NOT NULL DEFAULT 'Clinician',
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS users_email_lower_idx
    ON public.users (lower(email))
    WHERE email <> '';

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
);

CREATE INDEX IF NOT EXISTS assessments_owner_patient_idx
    ON public.assessments (owner_username, patient_id, observation_date ASC, recorded_at ASC);

CREATE INDEX IF NOT EXISTS assessments_patient_date_idx
    ON public.assessments (patient_id, observation_date ASC);

-- Row-Level Security (RLS): enforce per-owner isolation at database layer
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS users_owner_isolation ON public.users;
CREATE POLICY users_owner_isolation ON public.users
    FOR ALL
    USING (
        username = current_setting('app.current_user', true)
        OR current_user IN ('postgres', 'service_role')
    )
    WITH CHECK (
        username = current_setting('app.current_user', true)
        OR current_user IN ('postgres', 'service_role')
    );

DROP POLICY IF EXISTS assessments_owner_isolation ON public.assessments;
CREATE POLICY assessments_owner_isolation ON public.assessments
    FOR ALL
    USING (
        owner_username = current_setting('app.current_user', true)
        OR current_user IN ('postgres', 'service_role')
    )
    WITH CHECK (
        owner_username = current_setting('app.current_user', true)
        OR current_user IN ('postgres', 'service_role')
    );

