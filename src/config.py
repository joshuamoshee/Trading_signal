from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    twelvedata_api_key: str
    telegram_owner_chat_id: int
    database_url: str
    anthropic_api_key: str = ""    # keep optional, no longer required
    gemini_api_key: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()