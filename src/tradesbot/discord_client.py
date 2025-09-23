# src/tradesbot/discord_client.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Iterable

import discord
from discord.errors import Forbidden, NotFound, HTTPException

from tradesbot.storage import append_message
from tradesbot.uploader import upload_all_days

log = logging.getLogger(__name__)


def make_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    return intents


class TradesClient(discord.Client):
    """Discord client that runs a one-pass history dump on startup."""

    def __init__(self, *, channel_ids: Iterable[int], since: datetime, print_authors: bool):
        super().__init__(intents=make_intents())
        self._channel_ids = list(channel_ids)
        self._since = since
        self._print_authors = print_authors

    async def setup_hook(self) -> None:
        # Schedule the one-shot fetch once the client is ready
        asyncio.create_task(
            fetch_history_once(
                self,
                self._channel_ids,
                self._since,
                print_authors=self._print_authors,
            )
        )


async def fetch_history_once(
    client: discord.Client,
    channel_ids: Iterable[int],
    since: datetime,
    print_authors: bool = True,
) -> None:
    """Fetch history from the given channels/threads since a timestamp, then upload JSONL to GCS."""
    await client.wait_until_ready()
    try:
        for cid in channel_ids:
            # fetch_channel also works when channel isn't cached
            try:
                ch = await client.fetch_channel(cid)
            except NotFound:
                log.warning("Channel %s not found (bad ID or bot not invited). Skipping.", cid)
                continue
            except Forbidden:
                log.warning("Channel %s exists but bot lacks permission (View/Read History). Skipping.", cid)
                continue
            except HTTPException as e:
                log.warning("HTTP error fetching channel %s: %s. Skipping.", cid, e)
                continue

            if isinstance(ch, discord.TextChannel):
                await _dump_text_channel(ch, since, print_authors)
            elif isinstance(ch, discord.Thread):
                await _dump_thread(ch, since, print_authors)
            elif isinstance(ch, discord.ForumChannel):
                # live threads
                for th in ch.threads:
                    await _dump_thread(th, since, print_authors)
                # archived public threads
                async for th in ch.archived_threads(limit=None, private=False):
                    await _dump_thread(th, since, print_authors)
            else:
                log.warning("Channel %s is unsupported type %s; skipping.", cid, type(ch).__name__)

        # === Upload cleaned JSONL to GCS ===
        try:
            uploaded = await asyncio.to_thread(upload_all_days)
            if uploaded:
                log.info("Uploaded %d JSONL files to GCS.", uploaded)
            else:
                log.info("No JSONL files found to upload.")
        except Exception as e:
            log.warning("Upload to GCS failed: %s", e)

    finally:
        # Always close so the aiohttp connector is released (prevents 'Unclosed connector' warnings)
        await client.close()


async def _dump_text_channel(ch: discord.TextChannel, since: datetime, print_authors: bool):
    log.info("Reading #%s (%s) since %s", ch.name, ch.id, since.isoformat())
    count = 0
    async for m in ch.history(after=since, oldest_first=True, limit=None):
        _print_msg(m, print_authors)
        count += 1
    log.info("Finished channel %s, messages read: %d", ch.id, count)


async def _dump_thread(th: discord.Thread, since: datetime, print_authors: bool):
    parent = th.parent.name if th.parent else "?"
    log.info("Reading thread %s (%s) in #%s since %s", th.name, th.id, parent, since.isoformat())
    count = 0
    async for m in th.history(after=since, oldest_first=True, limit=None):
        _print_msg(m, print_authors)
        count += 1
    log.info("Finished thread %s, messages read: %d", th.id, count)


def _print_msg(m: discord.Message, print_authors: bool):
    author = f"{m.author}" if print_authors else ""
    line = (m.content or "").replace("\n", " ").strip()[:400]
    ts = m.created_at.isoformat()
    print(f"[{ts}] {author+': ' if author else ''}{line}")
    # Persist cleaned JSONL for summarization
    append_message(m)
