"""
Tests for FastAPI app structure and webhook endpoint (no live bot required).
"""
from pathlib import Path


def test_main_py_exists():
    assert Path("app/main.py").exists()


def test_dockerfile_exists():
    assert Path("Dockerfile").exists()


def test_dockerfile_uses_python311():
    text = Path("Dockerfile").read_text()
    assert "python:3.11" in text, "Dockerfile should use Python 3.11"


def test_dockerfile_runs_migrations():
    text = Path("Dockerfile").read_text()
    assert "alembic upgrade head" in text, "Dockerfile CMD must run alembic upgrade head"


def test_main_defines_health_endpoint():
    text = Path("app/main.py").read_text()
    assert "/health" in text, "app/main.py must define /health endpoint"


def test_main_defines_webhook_endpoint():
    text = Path("app/main.py").read_text()
    assert "telegram_webhook" in text or "webhook" in text.lower()


def test_main_validates_secret_token():
    text = Path("app/main.py").read_text()
    assert "webhook_secret" in text, "Webhook must validate secret token"


def test_bot_router_exists():
    assert Path("app/bot/router.py").exists()


def test_start_handler_exists():
    assert Path("app/bot/handlers/start.py").exists()


def test_start_handler_uses_get_or_create():
    text = Path("app/bot/handlers/start.py").read_text()
    assert "get_or_create" in text, "start handler must call UserService.get_or_create"
