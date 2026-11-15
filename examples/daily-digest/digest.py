"""digest.py — the user's side of the daily-digest example.

Every morning a scheduled prompt, ``[routine] build the daily digest``, asks the AI to read
``inbox.json``, sort the items by their ``priority`` field (1 first) and write ``digest.md``.
This script holds only the user's own act: ``python3 digest.py publish`` copies the digest
into ``published/digest-<date>.md`` once the user has read it and wants it kept.

Usage: ``python3 digest.py publish [--date YYYY-MM-DD]``
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def publish(day: str) -> int:
    digest = HERE / "digest.md"
    if not digest.is_file():
        print("no digest.md to publish: the morning routine has not written one yet.")
        return 1
    target = HERE / "published" / f"digest-{day}.md"
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(digest, target)
    print(f"published {target.name}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="digest.py")
    sub = parser.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("publish", help="keep today's digest.md under published/")
    p.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args(argv)
    return publish(args.date)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
