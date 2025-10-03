from dataclasses import dataclass
from datetime import datetime, timezone
import os


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Settings:
    token: str
    channel_ids: list[int]
    since_utc: datetime | None
    print_authors: bool


def load_settings() -> Settings:
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN missing. Add it to your .env")

    ch_raw = os.getenv("CHANNEL_IDS", "")
    if not ch_raw.strip():
        raise RuntimeError("CHANNEL_IDS missing (comma-separated channel IDs)")
    channel_ids = [int(x.strip()) for x in ch_raw.split(",") if x.strip()]

    since_str = os.getenv("SINCE_UTC_DATE", "").strip()
    since = None
    if since_str:
        since = datetime.fromisoformat(since_str).replace(tzinfo=timezone.utc)
    else:
        # default: last 24 hours (for daily job runs)
        # This ensures we capture a full day's messages
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)

    return Settings(
        token=token,
        channel_ids=channel_ids,
        since_utc=since,
        print_authors=_env_bool("PRINT_AUTHORS", True),
    )


