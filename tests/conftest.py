"""Shared by every test of harness-review.

1. The reader folder (``skills/harness-review/reader``) and this tests folder go on sys.path,
   so tests import ``transcritos`` and ``fabrica`` by name.
2. Every test gets ``IA_CODIGO_PROJETOS_DIR``, ``HOME`` and ``CLAUDE_CONFIG_DIR`` pointing at
   folders under ``tmp_path``, and ``CLAUDE_CODE_SESSION_ID`` removed, so no default path can
   reach the real transcripts.
3. In-process tests read and show times in ``fabrica.FUSO_TESTE`` (``define_fuso``), reset to
   the machine's rules after each test; subprocess tests pass ``--fuso FUSO_TESTE``.
4. No real-state hash guard: the reader has no state files of its own and only reads.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

LEITOR = pathlib.Path(__file__).resolve().parents[1] / "skills" / "harness-review" / "reader"
TESTES = pathlib.Path(__file__).resolve().parent

for _p in (LEITOR, TESTES):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import transcritos  # noqa: E402
from fabrica import FUSO_TESTE  # noqa: E402


@pytest.fixture(autouse=True)
def isola(tmp_path, monkeypatch):
    pasta = tmp_path / "projetos" / "-fixture"
    pasta.mkdir(parents=True)
    monkeypatch.setenv("IA_CODIGO_PROJETOS_DIR", str(pasta))
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return pasta


@pytest.fixture(autouse=True)
def fuso_de_teste():
    transcritos.define_fuso(FUSO_TESTE)
    yield
    transcritos.define_fuso(None)


@pytest.fixture
def pasta(isola):
    return isola
