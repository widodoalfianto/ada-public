from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import sys
import os

class BaseConfig(BaseSettings):
    """
    Base configuration class used by all services.
    Enforces environment separation and validation rules.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    # Environment Flags
    TEST_MODE: bool = False
    LOG_LEVEL: str = "INFO"

    # Infrastructure
    DATABASE_URL: str
    REDIS_URL: Optional[str] = "redis://redis:6379/0"

    # Service URLs (Internal)
    DATA_SERVICE_URL: str = "http://data-service:8000"
    INDICATOR_SERVICE_URL: str = "http://indicator-service:8000"
    SCANNER_SERVICE_URL: str = "http://scanner-service:8000"
    ALERT_SERVICE_URL: str = "http://alert-service:8000"

    def model_post_init(self, __context):
        """
        Run validation checks after settings are loaded.
        """
        self.validate_environment()

    def validate_environment(self):
        """
        Enforce strict separation rules between Dev (TEST_MODE=True) and Prod.
        """
        db_name = self.DATABASE_URL.split("/")[-1].split("?")[0]

        if self.TEST_MODE:
            # DEV/TEST MODE CHECKS
            try:
                print("⚠️  STARTING IN TEST/DEV MODE ⚠️")
            except UnicodeEncodeError:
                 print("STARTING IN TEST/DEV MODE")
            
            # 1. Database Name Validation
            # Dev should NEVER connect to 'stock_db' (which is reserved for Prod)
            # Exception: if using localhost/different port, but name checking is safer.
            if db_name == "stock_db":
                raise ValueError("SAFETY CHECK FAILED: Dev environment cannot use 'stock_db'. Rename to 'stock_dev_db'.")

        else:
            # PROD MODE CHECKS
            try:
                print("🚀 STARTING IN PRODUCTION MODE 🚀")
            except UnicodeEncodeError:
                print("STARTING IN PRODUCTION MODE")

            # 1. Database Name Validation
            if db_name != "stock_db":
                print(f"WARNING: Production seems to be using non-standard DB: {db_name}")

            # 2. Safety Banner
            print("==================================================")
            print("   PRODUCTION ENVIRONMENT - LIVE TRADING ACTIVE   ")
            print("==================================================")
