from shared.config import BaseConfig
from pydantic_settings import SettingsConfigDict

class Settings(BaseConfig):
    # Specialized: Alert Service Specific
    DISCORD_BOT_TOKEN: str

    # Specific Channels (Prod)
    DISCORD_CHANNEL_ESM: int = 0
    DISCORD_CHANNEL_MA: int = 0  # Legacy alias for ESM
    DISCORD_CHANNEL_PF: int = 0

    # Specific Channels (Test)
    DISCORD_CHANNEL_TEST_ESM: int = 0
    DISCORD_CHANNEL_TEST_MA: int = 0  # Legacy alias for ESM
    DISCORD_CHANNEL_TEST_PF: int = 0
    DISCORD_CHANNEL_TEST_FALLBACK: int = 0
    DISCORD_CHANNEL_TEST_SYSTEM: int = 0

    # Fallback
    DISCORD_CHANNEL_FALLBACK: int = 0
    # System
    DISCORD_CHANNEL_SYSTEM: int = 0

    # Guild ID for instant slash command sync
    DISCORD_GUILD_ID: int = 0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )

    def model_post_init(self, __context):
        # 1. Base Validation
        super().model_post_init(__context)

        # 2. Backward-compatible aliases
        if not self.DISCORD_CHANNEL_ESM and self.DISCORD_CHANNEL_MA:
            self.DISCORD_CHANNEL_ESM = self.DISCORD_CHANNEL_MA
        if not self.DISCORD_CHANNEL_TEST_ESM and self.DISCORD_CHANNEL_TEST_MA:
            self.DISCORD_CHANNEL_TEST_ESM = self.DISCORD_CHANNEL_TEST_MA

        # 3. Alert Logic
        if self.TEST_MODE:
            self.DISCORD_CHANNEL_ESM = self.DISCORD_CHANNEL_TEST_ESM
            self.DISCORD_CHANNEL_PF = self.DISCORD_CHANNEL_TEST_PF
            self.DISCORD_CHANNEL_FALLBACK = self.DISCORD_CHANNEL_TEST_FALLBACK
            self.DISCORD_CHANNEL_SYSTEM = self.DISCORD_CHANNEL_TEST_SYSTEM

settings = Settings()
