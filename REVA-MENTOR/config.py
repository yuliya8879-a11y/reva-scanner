"""
Маркетинговая система для @Eye888888_bot
Переменные окружения и общие настройки
"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    # Telegram
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID", "@Reva_mentor")  # канал для публикации
    admin_id: int = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

    # Claude API
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    content_model: str = "claude-haiku-4-5-20251001"   # Haiku для контента (дёшево)
    trends_model: str = "claude-sonnet-4-6"             # Sonnet для анализа трендов

    # Ниша
    niche: str = "диагностика блоков, бизнес-разбор, личностный рост, нумерология"
    brand_name: str = "Юлия Рева — Глаз Бога"
    target_audience: str = "предприниматели и эксперты, которые хотят расти без выгорания"

    # Контент
    post_language: str = "ru"
    reels_duration_seconds: int = 30   # целевая длина рилс

    # Тренды
    trend_sources: list = None

    def __post_init__(self):
        if self.trend_sources is None:
            self.trend_sources = [
                "маркетинг в Telegram 2025",
                "продвижение экспертов Instagram",
                "диагностика блоков тренды",
                "нумерология бизнес",
                "личный бренд эксперта",
            ]


config = Config()
