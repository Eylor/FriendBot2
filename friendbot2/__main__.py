"""Entry point: ``python -m friendbot2 [image|chat]``."""

import argparse
import logging
import sys

from . import config
from .bot import FriendBot


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="friendbot2",
        description="Run FriendBot2 in image-generation or persona-chat mode.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["image", "chat"],
        default=None,
        help="Which application to run (default: FRIENDBOT_MODE env var, then 'image').",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if not config.TOKEN:
        sys.exit(
            "FRIENDBOT_TOKEN is not set. Copy .env.example to .env and fill it in, "
            "or export FRIENDBOT_TOKEN in your environment."
        )

    bot = FriendBot(mode=args.mode)
    bot.run(config.TOKEN, log_handler=None)  # we configure logging above


if __name__ == "__main__":
    main()
