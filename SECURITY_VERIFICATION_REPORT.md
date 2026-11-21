# NEFROAI-X — Healthcare Software Security Verification Report

**Document Version:** 1.0.0  
**Audit Date:** November 21, 2026  
**Auditor:** Healthcare Information Security Reviewer  
**Standard References:** OWASP Top 10, CWE-1236 (Formula Injection), HIPAA Technical Safeguards (45 CFR § 164.312)

---

## 1. Security Architecture & Threat Model

NEFROAI-X is designed to process Protected Health Information (PHI) and clinical laboratory parameters. The application implements defense-in-depth measures across the transport, application, and persistence layers.

```
       [Client Browser (React SPA)]
                  │  HTTPS (TLS 1.3)
                  ▼
       [FastAPI Application Gateway]
         ├─ Strict CORS Policy (RegEx: https://.*\.onrender\.com)
         ├─ Bearer Token Verification (URLSafeTimedSerializer)
         └─ Input Schema Validation (Pydantic v2)
                  │
     ┌────────────┴────────────┐
     ▼                         ▼
[Persistence Layer]   [Export Engine]
  ├─ User Scoping       └─ CWE-1236 Sanitization
  ├─ PBKDF2 Password Hashing
  └─ Database Failover (Postgres -> SQLite)
```

---

## 2. Security Controls Verification

### 2.1 Authentication & Session Token Durability
* **Password Hashing:**
  * Password storage implements PBKDF2-HMAC-SHA256 with 260,000 iterations and a cryptographically secure 16-byte salt per user.
  * Plaintext passwords are never stored, transmitted in response payloads, or logged.
* **Token Durability Across Restarts:**
  * Session tokens are signed via `URLSafeTimedSerializer` with a fixed cloud secret key (`NEFROAI_JWT_SECRET` / `SECRET_KEY` / `.session_secret`).
  * Tokens remain valid across container restarts for the configured TTL (`86400 seconds` / 24 hours), eliminating the previous issue where application restarts invalidated active clinician sessions.
* **Cryptographic Tamper Resistance:**
  * Tampered token signatures or expired tokens are immediately intercepted and rejected with HTTP 401 (`Invalid or expired authentication token`).

---

### 2.2 Multi-Tenant Clinical Data Isolation
* **Tenant Scoping:**
  * Patient assessments in `ClinicalHistoryStore` are strictly partitioned by `owner_username`.
  * The query interface (`GET /api/history`) enforces user-level filtering:
    ```sql
    SELECT * FROM patient_assessments WHERE owner_username = :username AND patient_id = :pid
    ```
* **Adversarial Verification:**
  * An automated cross-tenant security test was executed where User A (`dr_smith`) and User B (`dr_jones`) saved records.
  * Attempting to query User A's patient records while authenticated as User B returned **0 records**, verifying zero cross-tenant leakage.

---

### 2.3 Injection Defense & CWE-1236 Formula Sanitization
* **Spreadsheet Formula Injection (CWE-1236):**
  * Clinical assessment exports (CSV format) can be opened in Microsoft Excel or Google Sheets. Attackers could theoretically craft malicious patient IDs (e.g. `=cmd|' /C calc'!A0`).
  * **Sanitization:** `sanitize_csv_cell()` inspects all alphanumeric fields. If a value begins with `=`, `+`, `-`, or `@`, a single quote (`'`) is prepended to neutralize formula execution.
  * **Verification:** Tested with adversarial strings `+SUM(1,1)`, `=1+1`, and `@import`. All were safely escaped.
* **SQL Injection:**
  * All database operations utilize parameterized queries through SQLAlchemy and Python sqlite3 interfaces. No raw string interpolation is used.

---

### 2.4 Container Hardening & Execution Privileges
* **Non-Root Execution:**
  * The production `Dockerfile` provisions a dedicated non-privileged user and group:
    ```dockerfile
    RUN groupadd -g 10001 appgroup && \
        useradd -u 10001 -g appgroup -s /sbin/nologin -d /app appuser
    USER appuser:appgroup
    ```
  * No root daemon, no sudo access, no unnecessary system utilities.
* **Network & Port Binding:**
  * Binds cleanly to the cloud-assigned environment port (`PORT`) via `uvicorn.run(..., host="0.0.0.0", port=port)`.
  * No unauthenticated debug ports or exposed SSH daemons.

---

### 2.5 Sensitive Data Exposure & Log Hygiene
* **Audit of System Logs:**
  * Evaluated startup logs, health check logs, and assessment execution logs.
  * Verified that patient laboratory inputs, passwords, JWT tokens, and secret keys are excluded from standard `INFO` and `DEBUG` logging streams.
  * SHA-256 attestation seals provide verifiable integrity without logging raw biomarker records.

---

## 3. Storage Security & Ephemeral SQLite Notice

When running in environments where external PostgreSQL is unreachable, the system automatically falls back to local SQLite (`runs/local_cdss.db`).

> [!WARNING]
> **Ephemeral Storage Notice:**  
> On container platforms without persistent block storage (such as Render Free Tier), local SQLite database files are wiped upon container restart or redeploy.  
> **Production Requirement:** For persistent, audit-compliant healthcare record retention, a production PostgreSQL connection string (`DATABASE_URL`) with automated point-in-time backups (PITR) must be provisioned.
