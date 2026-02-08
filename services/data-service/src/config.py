from shared.config import BaseConfig

class Settings(BaseConfig):
    FINNHUB_API_KEY: str
    
settings = Settings()
