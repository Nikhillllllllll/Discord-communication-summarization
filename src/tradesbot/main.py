import logging
from dotenv import load_dotenv
from tradesbot.config import load_settings
from tradesbot.logging_config import setup_logging
from tradesbot.discord_client import TradesClient


def main() -> None:
    load_dotenv()
    setup_logging(logging.INFO)
    cfg = load_settings()
    client = TradesClient(
        channel_ids=cfg.channel_ids,
        since=cfg.since_utc,
        print_authors=cfg.print_authors,
    )
    # Use discord.py's run() which manages the event loop and cleanup
    client.run(cfg.token)

if __name__ == "__main__":
    main()
