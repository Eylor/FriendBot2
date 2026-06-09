"""Entry point: ``python -m friendbot2``."""

import logging
import sys

from . import config
from .bot import FriendBot


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if not config.TOKEN:
        sys.exit(
            "FRIENDBOT_TOKEN is not set. Copy .env.example to .env and fill it in, "
            "or export FRIENDBOT_TOKEN in your environment."
        )

    bot = FriendBot()
    bot.run(config.TOKEN, log_handler=None)  # we configure logging above


if __name__ == "__main__":
    main()
