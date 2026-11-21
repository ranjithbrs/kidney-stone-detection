"""Safety verification tests for database storage classification, ephemeral indicators, and failover."""

import os
import pytest
from src.clinical.patient_store import ClinicalHistoryStore
import backend.main as bmain


def test_sqlite_explicitly_classified_as_ephemeral(tmp_path):
    """Verify that local SQLite is classified as DEMONSTRATION_EPHEMERAL with is_ephemeral=True."""
    db_file = os.path.join(tmp_path, "test_ephemeral.db")
    store = ClinicalHistoryStore(db_path=db_file)
    try:
        assert store.storage_backend == "sqlite"
        assert store.is_ephemeral is True
        assert store.storage_classification == "DEMONSTRATION_EPHEMERAL"
    finally:
        store.close()


def test_health_check_surfaces_ephemeral_warning(monkeypatch, tmp_path):
    """Verify that /api/health exposes clear ephemeral warnings when running on SQLite."""
    db_file = os.path.join(tmp_path, "health_test.db")
    mock_store = ClinicalHistoryStore(db_path=db_file)
    monkeypatch.setattr(bmain, "get_store", lambda: mock_store)
    monkeypatch.setenv("ENVIRONMENT", "development")

    health = bmain.health_check()
    try:
        assert health["storage_backend"] == "sqlite"
        assert health["is_ephemeral_demo"] is True
        assert health["storage_classification"] == "DEMONSTRATION_EPHEMERAL"
        assert health["ephemeral_warning"] is not None
        assert "DEMONSTRATION mode" in health["ephemeral_warning"]
        assert "DATABASE_URL" in health["ephemeral_warning"]
    finally:
        mock_store.close()


def test_failing_postgres_url_falls_back_safely_to_sqlite(tmp_path):
    """Verify that an unreachable PostgreSQL URL falls back gracefully to SQLite with error recorded."""
    # Port 59999 with zero timeout guarantees connection refused / timeout
    failing_url = "postgresql://invalid_user:invalid_pass@127.0.0.1:59999/invalid_db?connect_timeout=1"
    fallback_file = os.path.join(tmp_path, "fallback.db")

    store = ClinicalHistoryStore(db_path=fallback_file, database_url=failing_url)
    try:
        assert store.storage_backend == "sqlite"
        assert store.is_ephemeral is True
        assert store.cloud_connection_error is not None
        assert store.storage_classification == "DEMONSTRATION_EPHEMERAL"

        # Verify database schema is still initialized and functional
        ok, msg = store.register_user("dr_fallback", "Secret123!", "Dr. Fallback", "Clinician")
        assert ok is True
        user = store.authenticate_user("dr_fallback", "Secret123!")
        assert user is not None
    finally:
        store.close()
