# discord-trades-mvp

Minimal, private Discord reader: fetch messages from specific channels and print them as text.

## Quickstart
1. Copy `.env.example` -> `.env` and fill in:
   - `DISCORD_BOT_TOKEN` (from Developer Portal)
   - `CHANNEL_IDS` (comma-separated channel IDs)
2. Ensure your bot has **Message Content** intent ON and channel perms: View Channel + Read Message History.
3. Install:
   ```bash
   # with pip
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   # or with uv
   # uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
   ```

4. Run:

   ```bash
   ./scripts/run_local.sh
   ```

   or

   ```bash
   python -m tradesbot.main
   ```

## Notes

* The app exits after one pass (cron-friendly). Adjust later for streaming.
* Keep `.env` out of git. Use `.env.example` to share expected keys.
