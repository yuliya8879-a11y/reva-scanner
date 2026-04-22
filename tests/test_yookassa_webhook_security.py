from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAtest_token_for_testing_only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("YOOKASSA_WEBHOOK_SECRET", "yooka-secret")

from app.main import app  # noqa: E402
from app.main import get_db_session  # noqa: E402


def _build_payload(event_id: str = "evt_1", paid: bool = True) -> dict:
    return {
        "id": event_id,
        "event": "payment.succeeded",
        "object": {
            "id": "pay_1",
            "status": "succeeded",
            "paid": paid,
            "amount": {"value": "3500.00"},
            "metadata": {
                "telegram_user_id": "123456789",
                "scan_id": "42",
                "scan_type": "personal",
            },
        },
    }


def _sign(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def test_yookassa_webhook_rejects_invalid_signature():
    payload = _build_payload()
    body = json.dumps(payload).encode("utf-8")
    headers = {"X-YooKassa-Signature": "bad-signature"}
    with patch("app.main.settings.yookassa_webhook_secret", "yooka-secret"), \
         patch("app.main.bot.get_webhook_info", new=AsyncMock(return_value=type("WH", (), {"url": "x"})())), \
         patch("app.main.bot.set_webhook", new=AsyncMock()), \
         patch("app.main.run_follow_up_loop", new=AsyncMock()), \
         patch("app.main.run_monitor_loop", new=AsyncMock()), \
         patch("app.main.bot.session.close", new=AsyncMock()):
        with TestClient(app) as client:
            response = client.post("/webhook/yookassa", data=body, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid YooKassa signature"


def test_yookassa_webhook_accepts_valid_signature_and_deduplicates():
    payload = _build_payload(event_id="evt_dupe")
    body = json.dumps(payload).encode("utf-8")
    headers = {"X-YooKassa-Signature": _sign("yooka-secret", body)}

    class _Session:
        async def execute(self, *_args, **_kwargs):
            class _Result:
                def scalar_one_or_none(self):
                    return None
            return _Result()

        async def commit(self):
            return None

    async def _override_db():
        yield _Session()

    app.dependency_overrides[get_db_session] = _override_db
    try:
        with patch("app.main.settings.yookassa_webhook_secret", "yooka-secret"), \
             patch("app.main.bot.get_webhook_info", new=AsyncMock(return_value=type("WH", (), {"url": "x"})())), \
             patch("app.main.bot.set_webhook", new=AsyncMock()), \
             patch("app.main.run_follow_up_loop", new=AsyncMock()), \
             patch("app.main.run_monitor_loop", new=AsyncMock()), \
             patch("app.main.bot.session.close", new=AsyncMock()), \
             patch("app.services.yookassa_service.parse_webhook", return_value={
                 "payment_id": "pay_1",
                 "paid": True,
                 "amount": "3500.00",
                 "telegram_user_id": 123456789,
                 "scan_id": 42,
                 "scan_type": "personal",
             }), \
             patch("app.services.payment_service.PaymentService.confirm_payment", new=AsyncMock()), \
             patch("app.main.bot.send_message", new=AsyncMock()):
            with TestClient(app) as client:
                first = client.post("/webhook/yookassa", data=body, headers=headers)
                second = client.post("/webhook/yookassa", data=body, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
    finally:
        app.dependency_overrides.clear()
