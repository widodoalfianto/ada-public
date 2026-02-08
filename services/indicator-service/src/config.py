from shared.config import BaseConfig

class Settings(BaseConfig):
    # Indicator service only needs BaseConfig properties (DB URL is in Base)
    pass
    
settings = Settings()
