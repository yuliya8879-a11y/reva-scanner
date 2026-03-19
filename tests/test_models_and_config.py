"""
TDD RED phase tests for Task 1: Config, database layer, and all four ORM models.
These tests verify importability and structure of the core modules.
"""
import pytest


def test_config_imports():
    """Settings class is importable from app.config."""
    from app.config import Settings, settings
    assert Settings is not None


def test_settings_has_required_fields():
    """Settings class has all required field annotations."""
    from app.config import Settings
    fields = Settings.model_fields
    assert "telegram_bot_token" in fields
    assert "webhook_base_url" in fields
    assert "webhook_secret" in fields
    assert "database_url" in fields
    assert "anthropic_api_key" in fields


def test_settings_has_database_url_async_property():
    """Settings has database_url_async property."""
    from app.config import Settings
    assert hasattr(Settings, "database_url_async")


def test_database_imports():
    """Base, engine, async_session_factory, get_db_session importable from app.database."""
    from app.database import Base, engine, async_session_factory, get_db_session
    assert Base is not None
    assert engine is not None
    assert async_session_factory is not None
    assert get_db_session is not None


def test_user_model_imports():
    """User importable from app.models.user."""
    from app.models.user import User
    assert User.__tablename__ == "users"


def test_user_model_columns():
    """User model has required columns."""
    from app.models.user import User
    cols = {c.name for c in User.__table__.columns}
    assert "id" in cols
    assert "telegram_id" in cols
    assert "username" in cols
    assert "full_name" in cols
    assert "birth_date" in cols
    assert "created_at" in cols
    assert "updated_at" in cols


def test_scan_model_imports():
    """Scan, ScanStatus, ScanType importable from app.models.scan."""
    from app.models.scan import Scan, ScanStatus, ScanType
    assert Scan.__tablename__ == "scans"
    assert ScanStatus.collecting == "collecting"
    assert ScanType.mini == "mini"


def test_payment_model_imports():
    """Payment importable from app.models.payment."""
    from app.models.payment import Payment
    assert Payment.__tablename__ == "payments"


def test_content_queue_model_imports():
    """ContentQueue importable from app.models.content_queue."""
    from app.models.content_queue import ContentQueue
    assert ContentQueue.__tablename__ == "content_queue"


def test_scan_has_use_alter_fk():
    """Scan model payment_id FK uses use_alter=True for circular FK guard."""
    from app.models.scan import Scan
    for col in Scan.__table__.columns:
        if col.name == "payment_id":
            for fk in col.foreign_keys:
                assert fk.use_alter is True, "payment_id FK must use use_alter=True"
            break
    else:
        pytest.fail("payment_id column not found in Scan model")
