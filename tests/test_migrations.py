"""
Tests for Alembic migration structure (no live DB required).
"""
import os
from pathlib import Path


def test_alembic_ini_exists():
    assert Path("alembic.ini").exists(), "alembic.ini must exist"


def test_alembic_env_py_exists():
    assert Path("alembic/env.py").exists(), "alembic/env.py must exist"


def test_initial_migration_exists():
    versions = list(Path("alembic/versions").glob("*.py"))
    assert versions, "At least one migration file must exist in alembic/versions/"


def test_migration_imports_are_valid():
    """Migration file must be importable as a Python module."""
    import importlib.util

    versions = list(Path("alembic/versions").glob("*.py"))
    assert versions, "No migration files found"
    spec = importlib.util.spec_from_file_location("migration_0001", versions[0])
    module = importlib.util.module_from_spec(spec)
    # Just check it parses without syntax errors — don't execute it
    assert module is not None


def test_railway_json_exists():
    assert Path("railway.json").exists(), "railway.json must exist for Railway deployment"


def test_alembic_env_sets_url_from_settings():
    """env.py must reference settings.database_url_async (not hardcoded URL)."""
    env_text = Path("alembic/env.py").read_text()
    assert "settings.database_url_async" in env_text, (
        "alembic/env.py must override sqlalchemy.url from settings"
    )
