# Discord Bot Separation Guide

## Why Separate Bots?
Using a single bot for both Production and Development runs the risk of:
1.  **Rate Limits:** Dev testing consuming your production message quota.
2.  **Spam:** A bug in dev logic sending thousands of alerts to your community.
3.  **Token Leakage:** Developers having access to the production bot token.

## Setup Instructions

### 1. Create a "Ada Dev" Application
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Click **New Application**.
3.  Name it `Ada Dev` (or similar).
4.  Go to the **Bot** tab and click **Add Bot**.
5.  **Recommended:** Uncheck "Public Bot" (so only you can invite it).

### 2. Get the Token
1.  In the **Bot** tab, click **Reset Token**.
2.  Copy the new token string.

### 3. Update Configuration
1.  Open your local `.env.dev` file.
2.  Replace the existing `DISCORD_BOT_TOKEN` with your new **Dev** token.
    ```ini
    # .env.dev
    DISCORD_BOT_TOKEN=your_new_dev_bot_token_here
    ```

### 4. Invite the Dev Bot
1.  Go to **OAuth2** > **URL Generator**.
2.  Select `bot` scope.
3.  Select permissions (Send Messages, Embed Links, etc.).
4.  Copy the URL and invite the bot to your **Test Server** (or a private channel category).

### 5. Verify
1.  Run `dev.bat`.
2.  Check the logs to ensure the bot logs in as `Ada Dev`.
3.  Production will continue to use the token in `.env.prod`.
