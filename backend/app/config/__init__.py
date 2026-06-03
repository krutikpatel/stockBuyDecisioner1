from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str = ""
    cache_ttl_price_seconds: int = 900
    cache_ttl_fundamentals_seconds: int = 86400
    log_level: str = "INFO"


settings = Settings()
