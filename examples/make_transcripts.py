"""make_transcripts.py — writes the synthetic transcripts of the daily-digest example.

Seven mornings, 2026-11-01 to 2026-11-07: each one a session opened by the scheduled prompt
``[routine] build the daily digest`` (read ``inbox.json``, write ``digest.md``). On 11-03 the
routine hands the long items to one sub-agent. On 11-02, 11-04 and 11-06 the user reads the
digest later and runs ``digest.py publish``; on 11-05 the user answers but skips it.
Usage numbers are made up. Times are UTC. Line ids come from ``fabrica.ids_fixos()``, so
every run writes the same bytes.

Usage:
  python3 -B examples/make_transcripts.py            # rewrite examples/transcripts/-example
  python3 -B examples/make_transcripts.py --check    # exit 0 if the files match, 1 if not
  --pasta <dir> writes (or checks) another folder instead.
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tests"))

import fabrica  # noqa: E402

PASTA = HERE / "transcripts" / "-example"
ABRE = "[routine] build the daily digest"
MODELO = "claude-opus-5-5"
ACTED = {2: "looks good, publish it", 4: "fine, publish", 6: "publish it please"}
SKIPPED = {5: "not today, thanks"}
SUB_AGENT_DAY = 3


@contextlib.contextmanager
def _utc() -> Iterator[None]:
    """fabrica reads its local times in FUSO; the example's times are UTC."""
    antes = fabrica.FUSO
    fabrica.FUSO = ZoneInfo("UTC")
    try:
        yield
    finally:
        fabrica.FUSO = antes


def _assistant(t: fabrica.Transcrito, ts: str, ref: str, texto: str,
               usage: dict[str, int], tool_uses: list[dict[str, Any]] | None = None
               ) -> None:
    """An assistant line with an explicit example text (fabrica's own text is for tests)."""
    msg = {"role": "assistant", "model": MODELO, "id": f"msg_{ref}",
           "content": [{"type": "text", "text": texto}, *(tool_uses or [])],
           "usage": usage}
    t._linha(t._base(ts, "assistant", None, message=msg, requestId=f"req_{ref}"))


def _day(pasta: Path, d: int) -> None:
    dia = f"2026-11-{d:02d}"
    sid = f"00000000-0000-4000-9000-{d:012d}"
    t = fabrica.sessao(pasta, sid)
    k = d * 1000  # made-up usage, a little different every day
    t.meta(f"{dia}T07:00:00", ABRE)
    _assistant(t, f"{dia}T07:00:04", f"{d}a", "Reading the inbox.",
               fabrica.uso(3, 9200 + k, 0, 60),
               [fabrica.tu(f"toolu_{d}a", "Read", file_path="inbox.json")])
    t.resultado(f"{dia}T07:00:05", f"toolu_{d}a", f"{4 + d} items")
    if d == SUB_AGENT_DAY:
        tid = f"toolu_{d}s"
        _assistant(t, f"{dia}T07:00:09", f"{d}s", "Two items are long; summarising them.",
                   fabrica.uso(2, 400, 9200 + k, 90),
                   [fabrica.tu(tid, "Agent", subagent_type="general-purpose",
                               description="Summarise long items",
                               prompt="Summarise inbox items 2 and 4 in one line each.")])
        aj = fabrica.ajudante(pasta, sid, "a00000000000003",
                              meta={"name": "summariser", "description": "Summarise long items",
                                    "agentType": "general-purpose", "toolUseId": tid})
        aj.humano(f"{dia}T07:00:10", "Summarise inbox items 2 and 4 in one line each.")
        _assistant(aj, f"{dia}T07:00:15", f"{d}s1", "Item 2: backup failed. Item 4: login broken.",
                   fabrica.uso(3, 5100, 0, 140))
        t.resultado(f"{dia}T07:00:16", tid, "Item 2: backup failed. Item 4: login broken.")
    _assistant(t, f"{dia}T07:00:20", f"{d}b", "Sorted by priority; writing the digest.",
               fabrica.uso(2, 700, 9600 + k, 420 + 10 * d),
               [fabrica.tu(f"toolu_{d}b", "Write", file_path="digest.md",
                           content=f"# Digest {dia}\n")])
    t.resultado(f"{dia}T07:00:21", f"toolu_{d}b", "File created: digest.md")
    _assistant(t, f"{dia}T07:00:25", f"{d}c", "The digest is in digest.md.",
               fabrica.uso(1, 300, 10300 + k, 30))
    if d in ACTED:
        t.humano(f"{dia}T08:{10 + d:02d}:00", ACTED[d])
        _assistant(t, f"{dia}T08:{10 + d:02d}:06", f"{d}d", "Publishing.",
                   fabrica.uso(3, 200, 10600 + k, 40),
                   [fabrica.tu(f"toolu_{d}d", "Bash", command="python3 digest.py publish")])
        t.resultado(f"{dia}T08:{10 + d:02d}:07", f"toolu_{d}d", f"published digest-{dia}.md")
    elif d in SKIPPED:
        t.humano(f"{dia}T09:00:00", SKIPPED[d])
        _assistant(t, f"{dia}T09:00:04", f"{d}d", "Leaving it unpublished.",
                   fabrica.uso(3, 150, 10600 + k, 15))


def gera(pasta: Path) -> None:
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)
    with _utc(), fabrica.ids_fixos():
        for d in range(1, 8):
            _day(pasta, d)


def _bytes(pasta: Path) -> dict[str, bytes]:
    return {p.relative_to(pasta).as_posix(): p.read_bytes()
            for p in sorted(pasta.rglob("*")) if p.is_file()}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="make_transcripts.py")
    parser.add_argument("--check", action="store_true",
                        help="regenerate into a temporary folder and compare; write nothing")
    parser.add_argument("--pasta", type=Path, default=PASTA)
    args = parser.parse_args(argv)
    if not args.check:
        gera(args.pasta)
        print(f"wrote {len(_bytes(args.pasta))} files into {args.pasta}")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        novo = Path(tmp) / "-example"
        gera(novo)
        esperado = _bytes(novo)
    atual = _bytes(args.pasta) if args.pasta.is_dir() else {}
    diferentes = sorted(n for n in esperado.keys() | atual.keys()
                        if esperado.get(n) != atual.get(n))
    if diferentes:
        print("differs from a fresh run: " + ", ".join(diferentes))
        return 1
    print(f"same bytes: {len(atual)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
