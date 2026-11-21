# NEFROAI-X — Phase 2 Automated Test & Quality Assurance Report

**Execution Date:** November 21, 2026  
**Test Runner:** pytest 8.3.4 (Python 3.10.0, Windows x64)  
**Frontend Builder:** Vite 6.4.6 / Node 20  
**Overall Test Result:** 🟢 **341 PASSED, 3 SKIPPED, 0 FAILED** (344 Total Tests)

---

## 1. Test Suite Summary

```
====================================================================================
                        NEFROAI-X TEST SUITE EXECUTION SUMMARY
====================================================================================
Tests Collected:        344
Tests Passed:           341 (99.1%)
Tests Skipped:          3   (0.9%)
Tests Failed:           0   (0.0%)
Execution Duration:     82.19 seconds
====================================================================================
```

---

## 2. Test Execution Breakdown by Module

| Test Module | Tests | Passed | Skipped | Failed | Coverage Focus |
|---|:---:|:---:|:---:|:---:|---|
| [tests/test_jwt_security.py](file:///c:/Users/B%20Ranjith/Downloads/project/tests/test_jwt_security.py) | 6 | 6 | 0 | 0 | JWT production requirement, dev fallback, signature validation, tamper rejection |
| [tests/test_storage_safety.py](file:///c:/Users/B%20Ranjith/Downloads/project/tests/test_storage_safety.py) | 3 | 3 | 0 | 0 | Storage classification (`DEMONSTRATION_EPHEMERAL`), health telemetry, failover |
| [tests/test_comprehensive_verification.py](file:///c:/Users/B%20Ranjith/Downloads/project/tests/test_comprehensive_verification.py) | 120 | 120 | 0 | 0 | Complete clinical calculation contracts, KDIGO staging, KFRE, XAI concordance |
| [tests/test_fullstack_api.py](file:///c:/Users/B%20Ranjith/Downloads/project/tests/test_fullstack_api.py) | 36 | 36 | 0 | 0 | FastAPI REST endpoints, auth signup/signin, batch screening, report export |
| [tests/test_option_ab_extensions.py](file:///c:/Users/B%20Ranjith/Downloads/project/tests/test_option_ab_extensions.py) | 125 | 123 | 2 | 0 | 10 clinical safety extensions (Conformal, Mondrian, Coherence, Drift, Trajectory) |
| [tests/test_invention_prototype.py](file:///c:/Users/B%20Ranjith/Downloads/project/tests/test_invention_prototype.py) | 54 | 53 | 1 | 0 | Candidate invention prototype (MIDR, CRI scoring, selective abstention) |

---

## 3. Audit of Skipped Tests

Three tests out of 344 were conditionally skipped by test harness decorators:

1. **`tests/test_invention_prototype.py::test_mysql_legacy_connection`**
   - *Status:* `SKIPPED`
   - *Reason:* The legacy MySQL authentication database (`App.py` targeting `localhost:3306`, table `regtb`) is not running as an active background service in the CI/test runner. The modern primary CDSS uses SQLite / PostgreSQL (`backend/main.py`), making local MySQL optional.
2. **`tests/test_option_ab_extensions.py::test_live_cloud_postgres_pool_connection`**
   - *Status:* `SKIPPED`
   - *Reason:* Direct external Supabase pooled connections require live network access and valid remote credentials (`DATABASE_URL`). When running offline or in sandboxed test environments, the test detects the unconfigured connection and gracefully skips to prevent artificial CI failure.
3. **`tests/test_option_ab_extensions.py::test_smtp_live_alert_delivery`**
   - *Status:* `SKIPPED`
   - *Reason:* Live email transmission is disabled in test mode to prevent sending synthetic test emails to real external SMTP servers (`ckdteam2027@gmail.com`).

---

## 4. Frontend Production Build Verification

The React 18 Single Page Application (SPA) was compiled using Vite:

```bash
> npm --prefix frontend run build

vite v6.4.6 building for production...
transforming...
✓ 1600 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.71 kB │ gzip:  0.41 kB
dist/assets/index-DSwU_hyZ.css   23.66 kB │ gzip:  5.20 kB
dist/assets/index-C711PK7i.js   265.59 kB │ gzip: 77.16 kB
✓ built in 3.92s
```

- **Compilation Status:** Clean exit code 0.
- **Bundle Integrity:** Generated `frontend/dist/index.html` and bundled CSS/JS assets without warnings or syntax errors.
- **Asset Size:** Gzipped JavaScript bundle is $77.16\text{ KB}$, ensuring fast mobile and clinic desktop initial loads.
- **Banner Inclusion:** Verified that `.public-demo-warning-banner` and associated CSS styles are bundled in the distribution build.
