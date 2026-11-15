"""The synthetic example: make_transcripts.py writes the same bytes every time, and --check
says so both ways. Every write goes to tmp_path; the committed files are only read."""
from __future__ import annotations

import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
GERADOR = RAIZ / "examples" / "make_transcripts.py"
EXEMPLO = RAIZ / "examples" / "transcripts" / "-example"


def roda(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(GERADOR), *args],
                          capture_output=True, text=True)


def arquivos(pasta: pathlib.Path) -> dict[str, bytes]:
    return {p.relative_to(pasta).as_posix(): p.read_bytes()
            for p in sorted(pasta.rglob("*")) if p.is_file()}


def test_duas_geracoes_dao_os_mesmos_bytes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert roda("--pasta", str(a)).returncode == 0
    assert roda("--pasta", str(b)).returncode == 0
    assert arquivos(a) == arquivos(b)
    assert len(arquivos(a)) == 9  # 7 main files + one sub-agent file and its meta


def test_exemplo_commitado_confere():
    r = roda("--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_falha_com_um_byte_trocado_e_com_arquivo_a_mais(tmp_path):
    pasta = tmp_path / "-example"
    roda("--pasta", str(pasta))
    assert roda("--check", "--pasta", str(pasta)).returncode == 0
    alvo = sorted(pasta.glob("*.jsonl"))[0]
    original = alvo.read_bytes()
    alvo.write_bytes(original[:-2] + b"X" + original[-1:])
    assert roda("--check", "--pasta", str(pasta)).returncode == 1
    alvo.write_bytes(original)
    (pasta / "extra.jsonl").write_text("{}\n")
    assert roda("--check", "--pasta", str(pasta)).returncode == 1


def test_exemplo_nao_tem_o_marcador_dos_testes():
    for nome, dados in arquivos(EXEMPLO).items():
        assert b"SENTINELA" not in dados, nome
