from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    webhook_secret: str = "change_me_32_char_random_string"
    webhook_base_url: str = "https://your-service.railway.app"
    database_url: str
    anthropic_api_key: str = ""
    anthropic_api_key_2: str = ""   # резервный ключ — автопереключение при исчерпании первого
    admin_telegram_id: int = 0

    @property
    def database_url_async(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def webhook_path(self) -> str:
        return "/webhook/telegram"

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url}{self.webhook_path}"


settings = Settings()
