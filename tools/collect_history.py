#!/usr/bin/env python3
"""
Pull message history from Discord into JSONL files for fine-tuning.

Logs in with the bot token, walks every readable text channel (optionally
filtered by guild/channel), and appends one JSON record per message to
``<out>/<guild_id>/<channel_id>.jsonl``, oldest first. Re-running resumes from
the last collected message in each file, so periodic top-ups are cheap.
Also writes ``users.json`` (author metadata) and ``channels.json`` per guild.

Threads and forum posts are not collected — plain text channels only.

Usage:
  python tools/collect_history.py                       # everything the bot can read
  python tools/collect_history.py --guild 1234          # one guild
  python tools/collect_history.py --channels 111 222    # specific channels
  python tools/collect_history.py --no-resume           # re-pull from the beginning

The token is read from FRIENDBOT_TOKEN (a .env file in the repo root works).
Requires the Message Content privileged intent, same as the bot itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import discord

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def record_for(message: discord.Message) -> dict:
    return {
        "id": message.id,
        "ts": message.created_at.isoformat(),
        "author_id": message.author.id,
        "author": message.author.display_name,
        "bot": message.author.bot,
        "content": message.content,
        # clean_content has user/channel mentions already resolved to names,
        # which is what build_dataset.py trains on.
        "clean": message.clean_content,
        "reply_to": message.reference.message_id if message.reference else None,
        "attachments": len(message.attachments),
    }


def last_timestamp(path: Path) -> datetime | None:
    """Timestamp of the last intact record in an existing JSONL file."""
    try:
        with open(path, "rb") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            return datetime.fromisoformat(json.loads(raw)["ts"])
        except (ValueError, KeyError):
            continue  # tolerate a truncated final line from an interrupted run
    return None


class Collector(discord.Client):
    def __init__(
        self,
        *,
        guild_id: int | None,
        channel_ids: set[int],
        out_dir: Path,
        resume: bool,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.guild_id = guild_id
        self.channel_ids = channel_ids
        self.out_dir = out_dir
        self.resume = resume

    async def on_ready(self) -> None:
        try:
            await self._collect()
        finally:
            await self.close()

    async def _collect(self) -> None:
        for guild in self.guilds:
            if self.guild_id and guild.id != self.guild_id:
                continue
            guild_dir = self.out_dir / str(guild.id)
            guild_dir.mkdir(parents=True, exist_ok=True)

            users = self._load_json(guild_dir / "users.json")
            channels_meta = self._load_json(guild_dir / "channels.json")

            for channel in guild.text_channels:
                if self.channel_ids and channel.id not in self.channel_ids:
                    continue
                perms = channel.permissions_for(guild.me)
                if not (perms.read_messages and perms.read_message_history):
                    print(f"  #{channel.name}: no read permission, skipping")
                    continue

                channels_meta[str(channel.id)] = {"name": channel.name}
                path = guild_dir / f"{channel.id}.jsonl"
                after = last_timestamp(path) if self.resume else None
                if after:
                    print(f"  #{channel.name}: resuming after {after.isoformat()}")
                else:
                    print(f"  #{channel.name}: collecting from the beginning")

                count = 0
                with open(path, "a" if after else "w", encoding="utf-8") as f:
                    async for message in channel.history(
                        limit=None, oldest_first=True, after=after
                    ):
                        f.write(json.dumps(record_for(message), ensure_ascii=False))
                        f.write("\n")
                        u = users.setdefault(
                            str(message.author.id),
                            {"name": message.author.display_name,
                             "bot": message.author.bot,
                             "messages": 0},
                        )
                        u["name"] = message.author.display_name
                        u["messages"] += 1
                        count += 1
                        if count % 2000 == 0:
                            print(f"    ... {count} messages")
                print(f"  #{channel.name}: {count} new message(s)")

            (guild_dir / "users.json").write_text(
                json.dumps(users, indent=2, ensure_ascii=False)
            )
            (guild_dir / "channels.json").write_text(
                json.dumps(channels_meta, indent=2, ensure_ascii=False)
            )
            print(f"{guild.name}: done -> {guild_dir}")

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--guild", type=int, default=None, help="Only this guild id")
    parser.add_argument(
        "--channels", type=int, nargs="*", default=[], help="Only these channel ids"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "raw",
        help="Output directory (default: data/raw)",
    )
    parser.add_argument(
        "--resume",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Continue from the last collected message per channel",
    )
    args = parser.parse_args()

    token = os.environ.get("FRIENDBOT_TOKEN", "")
    if not token:
        sys.exit("FRIENDBOT_TOKEN is not set (put it in .env or the environment).")

    intents = discord.Intents.default()
    intents.message_content = True

    client = Collector(
        guild_id=args.guild,
        channel_ids=set(args.channels),
        out_dir=args.out,
        resume=args.resume,
        intents=intents,
    )
    client.run(token)


if __name__ == "__main__":
    main()
