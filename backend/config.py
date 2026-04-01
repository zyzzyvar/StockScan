from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="/Users/zyzbot/MyProject/StockScan/.env",
        env_file_encoding="utf-8",
    )

    stockscan_db_url: str = "postgresql+psycopg2://stockscan_user:stockscan_pass@localhost:5432/stockscan"
    stockdb_url: str = "postgresql+psycopg2://stockscan_user:stockscan_pass@localhost:5432/stockdb"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
