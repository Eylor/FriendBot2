#!/usr/bin/env python3
"""
Turn raw collected history (tools/collect_history.py output) into an SFT dataset.

The model is trained completion-style on chat transcripts: contiguous runs of
messages are rendered one per line as ``Name: message`` and chunked into
samples of roughly --chunk-chars characters (with a few lines of overlap so no
exchange is ever split learn-nothing-from-it). Long silences (--gap-minutes)
start a new session so unrelated conversations don't get glued together.

Filtering: bot authors, command invocations (!..., /...), empty/attachment-only
messages, and over-long pastes are dropped or truncated. Custom emoji are
reduced to :name:. Internal newlines become spaces (one message == one line).

Outputs in --out (default data/sft):
  train.jsonl / val.jsonl   {"text": "<transcript chunk>"} per line
  personas.json             users by message count (most active first); the bot
                            reads this to know which personas it can mimic

Usage:
  python tools/build_dataset.py
  python tools/build_dataset.py --raw data/raw --out data/sft --chunk-chars 4000
"""

from __future__ import annotations

import argparse
import json
import random
import re
from datetime import datetime
from pathlib import Path

_CUSTOM_EMOJI = re.compile(r"<a?(:\w+:)\d+>")
COMMAND_PREFIXES = ("!", "/", "$", ".")


def normalize(text: str) -> str:
    text = _CUSTOM_EMOJI.sub(r"\1", text)
    return " ".join(text.split())


def load_channel(path: Path, max_msg_chars: int) -> list[tuple[datetime, str, str]]:
    """Read one channel JSONL into (timestamp, author, text) tuples, filtered."""
    out: list[tuple[datetime, str, str]] = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if rec.get("bot"):
                continue
            text = normalize(rec.get("clean") or rec.get("content") or "")
            if not text or text.startswith(COMMAND_PREFIXES):
                continue
            if len(text) > max_msg_chars:
                text = text[:max_msg_chars] + " ..."
            try:
                ts = datetime.fromisoformat(rec["ts"])
            except (KeyError, ValueError):
                continue
            out.append((ts, rec.get("author") or "unknown", text))
    out.sort(key=lambda t: t[0])
    return out


def split_sessions(
    messages: list[tuple[datetime, str, str]], gap_minutes: int
) -> list[list[tuple[str, str]]]:
    """Split a channel's messages into conversation sessions on long silences."""
    sessions: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    prev_ts: datetime | None = None
    for ts, author, text in messages:
        if prev_ts is not None and (ts - prev_ts).total_seconds() > gap_minutes * 60:
            if current:
                sessions.append(current)
            current = []
        current.append((author, text))
        prev_ts = ts
    if current:
        sessions.append(current)
    return sessions


def chunk_session(
    session: list[tuple[str, str]], chunk_chars: int, overlap_lines: int
) -> list[str]:
    """Greedily pack a session's lines into ~chunk_chars text samples."""
    lines = [f"{author}: {text}" for author, text in session]
    chunks: list[str] = []
    start = 0
    while start < len(lines):
        size = 0
        end = start
        while end < len(lines) and (size + len(lines[end]) + 1 <= chunk_chars or end == start):
            size += len(lines[end]) + 1
            end += 1
        chunks.append("\n".join(lines[start:end]))
        if end >= len(lines):
            break
        start = max(end - overlap_lines, start + 1)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--raw", type=Path, default=repo_root / "data" / "raw")
    parser.add_argument("--out", type=Path, default=repo_root / "data" / "sft")
    parser.add_argument("--chunk-chars", type=int, default=4000,
                        help="Approximate characters per training sample (~1k tokens)")
    parser.add_argument("--overlap-lines", type=int, default=4)
    parser.add_argument("--gap-minutes", type=int, default=240,
                        help="Silence longer than this starts a new session")
    parser.add_argument("--min-session-lines", type=int, default=3)
    parser.add_argument("--max-msg-chars", type=int, default=800)
    parser.add_argument("--val-fraction", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    channel_files = sorted(args.raw.glob("*/*.jsonl"))
    if not channel_files:
        raise SystemExit(
            f"No raw history found under {args.raw} — run tools/collect_history.py first."
        )

    chunks: list[str] = []
    persona_counts: dict[str, int] = {}
    total_msgs = kept_msgs = 0

    for path in channel_files:
        messages = load_channel(path, args.max_msg_chars)
        kept_msgs += len(messages)
        total_msgs += sum(1 for _ in open(path, encoding="utf-8"))
        for _, author, _ in messages:
            persona_counts[author] = persona_counts.get(author, 0) + 1
        for session in split_sessions(messages, args.gap_minutes):
            if len(session) < args.min_session_lines:
                continue
            chunks.extend(chunk_session(session, args.chunk_chars, args.overlap_lines))

    if not chunks:
        raise SystemExit("Nothing survived filtering — check the raw data.")

    rng = random.Random(args.seed)
    rng.shuffle(chunks)
    n_val = max(1, int(len(chunks) * args.val_fraction))
    val, train = chunks[:n_val], chunks[n_val:]

    args.out.mkdir(parents=True, exist_ok=True)
    for name, split in (("train.jsonl", train), ("val.jsonl", val)):
        with open(args.out / name, "w", encoding="utf-8") as f:
            for text in split:
                f.write(json.dumps({"text": text}, ensure_ascii=False))
                f.write("\n")

    personas = [
        {"name": name, "messages": count}
        for name, count in sorted(persona_counts.items(), key=lambda kv: -kv[1])[:50]
    ]
    (args.out / "personas.json").write_text(
        json.dumps(personas, indent=2, ensure_ascii=False)
    )

    print(f"Messages: {total_msgs} read, {kept_msgs} kept after filtering")
    print(f"Samples:  {len(train)} train, {len(val)} val -> {args.out}")
    print("Top personas:")
    for p in personas[:10]:
        print(f"  {p['name']:24s} {p['messages']}")


if __name__ == "__main__":
    main()
