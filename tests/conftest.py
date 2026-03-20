"""Shared pytest fixtures and environment setup.

Sets minimal env vars so that pydantic-settings can load Settings()
without a real .env file. Must run before any app module is imported.
"""

import os

# Set required env vars BEFORE any app module is imported.
# These are test-only stubs — no real services are called.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAtest_token_for_testing_only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
