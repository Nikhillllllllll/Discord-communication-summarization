# src/tradesbot/storage.py
from __future__ import annotations
import json, re
from pathlib import Path
from datetime import timezone
import discord

# Ephemeral path inside the container
BASE = Path("/tmp/ingest")

# simple cleanup
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF]")
WS_RE = re.compile(r"\s+")

def _clean(s: str) -> str:
    s = EMOJI_RE.sub("", s or "")
    s = s.replace("```", "").replace("`", "")
    s = WS_RE.sub(" ", s).strip()
    return s

def _day_dir(ts_utc):
    day = ts_utc.astimezone(timezone.utc).date().isoformat()
    p = BASE / day
    p.mkdir(parents=True, exist_ok=True)
    return p

def append_message(m: discord.Message) -> None:
    content = _clean(m.content)
    if not content:
        return  # skip empty after cleanup
    rec = {
        "ts": m.created_at.replace(tzinfo=timezone.utc).isoformat(),
        "channel_id": str(m.channel.id),
        "channel_name": getattr(m.channel, "name", None),
        "author_id": str(m.author.id),
        "author": str(m.author),
        "content": content,
        "urls": (
            [a.url for a in m.attachments] +
            ([u for u in (m.content or "").split() if u.startswith(("http://","https://"))])
        ),
    }
    out = _day_dir(m.created_at) / f"{m.channel.id}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
