"""mede.py through the real command line: the answer, and every exit-2 case with no traceback
and nothing on stdout."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fabrica import FUSO_TESTE, SENTINELA, sessao, tu, uso

import transcritos as tr

MEDE = Path(__file__).resolve().parents[1] / "skills" / "harness-review" / "reader" / "mede.py"
ROTINA = r"texto:^\[routine\] read queue/next\.md"
TXT_ROTINA = f"[routine] read queue/next.md {SENTINELA}"
FRASE = ("diga qual é a sessão desta medição e quando ela começou "
         "(--sessao-propria … --desde …) ou --sem-sessao-propria")
JANELA = ["--de", "2026-11-10", "--ate", "2026-11-12"]


def roda(*args: str, fuso: str | None = FUSO_TESTE, cwd: Path | None = None,
         **env: str) -> subprocess.CompletedProcess:
    """The CLI as a member runs it; env is the conftest's (plus ``env``), so only tmp folders
    are reachable. ``fuso=None`` leaves ``--fuso`` out."""
    zona = ["--fuso", fuso] if fuso is not None else []
    return subprocess.run([sys.executable, "-B", str(MEDE), "execucoes", *zona, *args],
                          capture_output=True, env={**os.environ, **env}, cwd=cwd, timeout=60)


def fixture(pasta: Path) -> None:
    s = sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA)
    s.assistente("2026-11-10T20:01", "r1", uso(entrada=5, relidos=100, escritos=10),
                 tool_uses=[tu("b1", command="tracker.py done 3")])
    s.resultado("2026-11-10T20:01:30", "b1")
    s.meta("2026-11-10T20:30", f'<channel source="chat">feito {SENTINELA}</channel>')
    s.assistente("2026-11-10T20:31", "r2", uso(escritos=20))
    s.meta("2026-11-11T08:00", TXT_ROTINA).assistente("2026-11-11T08:01", "r3")
    # the measuring session: its later lines must stay out
    sessao(pasta, "medindo").humano("2026-11-11T09:00") \
        .meta("2026-11-11T09:30", TXT_ROTINA).assistente("2026-11-11T09:31", "r4")


# ---------------------------------------------------------------- the answer


def test_responde_json_ordenado_com_regua(pasta):
    fixture(pasta)
    r = roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria",
             "--resposta", r'source="chat"', "--acao", r"comando:tracker\.py done")
    assert r.returncode == 0, r.stderr.decode("utf-8")
    texto = r.stdout.decode("utf-8")
    dados = json.loads(texto)
    assert texto == json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    assert len(dados["execucoes"]) == 3
    primeira = dados["execucoes"][0]
    assert primeira["sessao"] == "s1" and primeira["respondido"] is True
    # the run's own tracker.py call is never the user's action on it
    assert primeira["agido"] is False and primeira["comandos"]["por_desfecho"] == {"ok": 1}
    assert dados["regua"]["fonte"] == str(pasta.resolve())  # default folder from the env
    assert dados["regua"]["regra_da_pasta"] == "variavel"
    assert dados["regua"]["fuso"] == FUSO_TESTE
    assert dados["regua"]["padroes"]["abre"] == ROTINA
    assert dados["regua"]["formato_mudou"] is False
    assert SENTINELA not in texto and SENTINELA not in r.stderr.decode("utf-8")


def test_sessao_propria_desde_com_fuso_deixa_de_fora_so_o_depois(pasta, tmp_path):
    fixture(pasta)
    outra = tmp_path / "outra"
    pasta.rename(outra)  # --pasta wins over the env's folder
    base = ["--pasta", str(outra), "--abre", ROTINA, *JANELA]
    sem = json.loads(roda(*base, "--sem-sessao-propria").stdout)
    local = json.loads(roda(*base, "--sessao-propria", "claude:medindo",
                            "--desde", "2026-11-11T09:15").stdout)
    iso = json.loads(roda(*base, "--sessao-propria", "medindo",
                          "--desde", "2026-11-11T14:15:00+00:00").stdout)
    assert len(sem["execucoes"]) == 3
    assert len(local["execucoes"]) == len(iso["execucoes"]) == 2
    assert local["regua"]["excluidas"] == ["medindo desde 2026-11-11T09:15:00-05:00"]
    assert iso["regua"]["excluidas"] == local["regua"]["excluidas"]


def test_exclui_sessao_repetivel_e_ate_so_data_vai_ao_fim_do_dia(pasta):
    fixture(pasta)
    sessao(pasta, "s9").meta("2026-11-12T23:58", TXT_ROTINA).assistente("2026-11-12T23:59", "r9")
    todas = json.loads(roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria").stdout)
    assert len(todas["execucoes"]) == 4  # the 23:58 run on the --ate day is in
    menos = json.loads(roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria",
                            "--exclui-sessao", "medindo", "--exclui-sessao", "s9").stdout)
    assert len(menos["execucoes"]) == 2
    assert menos["regua"]["excluidas"] == ["medindo", "s9"]


# ---------------------------------------------------------------- exit 2


@pytest.mark.parametrize("forma", [
    [],
    ["--sessao-propria", "abc"],
    ["--desde", "2026-11-11T09:00"],
    ["--sem-sessao-propria", "--sessao-propria", "abc", "--desde", "2026-11-11T09:00"],
])
def test_sem_a_forma_da_sessao_propria_sai_2_com_a_frase(pasta, forma):
    fixture(pasta)
    r = roda("--abre", ROTINA, *JANELA, *forma)
    assert r.returncode == 2
    assert r.stdout == b""
    assert r.stderr.decode("utf-8").strip() == FRASE


@pytest.mark.parametrize("args,trecho", [
    (["--de", "10/11/2026", "--ate", "2026-11-12", "--sem-sessao-propria"], "--de"),
    (["--de", "2026-11-10", "--ate", "2026-13-01", "--sem-sessao-propria"], "--ate"),
    (["--de", "2026-11-10", "--ate", "2026-11-12", "--sessao-propria", "x",
      "--desde", "ontem"], "--desde"),
    (["--de", "2026-11-10", "--ate", "2026-11-12", "--sessao-propria", "x",
      "--desde", "2026-11-11T09:00:00"], "--desde"),  # ISO without an offset
    (["--de", "2026-11-12", "--ate", "2026-11-10", "--sem-sessao-propria"], "ao contrário"),
])
def test_data_ruim_sai_2(pasta, args, trecho):
    fixture(pasta)
    r = roda("--abre", ROTINA, *args)
    erro = r.stderr.decode("utf-8")
    assert r.returncode == 2 and r.stdout == b""
    assert trecho in erro and "Traceback" not in erro


def test_pasta_ausente_sai_2(tmp_path):
    r = roda("--pasta", str(tmp_path / "nao-existe"), "--abre", ROTINA, *JANELA,
             "--sem-sessao-propria")
    erro = r.stderr.decode("utf-8")
    assert r.returncode == 2 and r.stdout == b""
    assert "não existe" in erro and "Traceback" not in erro


@pytest.mark.parametrize("args", [
    ["--abre", "texto:("],
    ["--abre", "rotina"],
    ["--abre", ROTINA, "--resposta", "["],
    ["--abre", ROTINA, "--acao", "texto:x"],
    ["--abre", ROTINA, "--fecha", "skill:x"],
])
def test_padrao_ruim_sai_2(pasta, args):
    fixture(pasta)
    r = roda(*args, *JANELA, "--sem-sessao-propria")
    erro = r.stderr.decode("utf-8")
    assert r.returncode == 2 and r.stdout == b""
    assert "padrão" in erro and "Traceback" not in erro


# ---------------------------------------------------------------- --fuso


def _tarde_da_noite(pasta: Path) -> None:
    """One run at 23:30 of the window's last day, in FUSO_TESTE (04:30 UTC the next day)."""
    sessao(pasta, "s1").meta("2026-11-12T23:30", TXT_ROTINA).assistente("2026-11-12T23:31", "r1")


def test_fuso_muda_a_janela(pasta):
    _tarde_da_noite(pasta)
    ny = json.loads(roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria").stdout)
    utc = json.loads(roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria", fuso="UTC").stdout)
    assert len(ny["execucoes"]) == 1 and ny["execucoes"][0]["inicio"] == \
        "2026-11-12T23:30:00-05:00"
    assert utc["execucoes"] == []  # 04:30 UTC on 13/11 is after a UTC window ending 12/11
    assert ny["regua"]["fuso"] == FUSO_TESTE and utc["regua"]["fuso"] == "UTC"
    assert utc["regua"]["janela"]["de"] == "2026-11-10T00:00:00+00:00"


@pytest.mark.skipif(sys.platform == "win32", reason="TZ in the environment is POSIX only")
def test_sem_fuso_usa_as_regras_do_computador(pasta):
    _tarde_da_noite(pasta)
    ny = json.loads(roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria", fuso=None,
                         TZ=FUSO_TESTE).stdout)
    utc = json.loads(roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria", fuso=None,
                          TZ="UTC").stdout)
    assert len(ny["execucoes"]) == 1 and utc["execucoes"] == []
    assert ny["regua"]["fuso"] == "local"
    assert ny["regua"]["janela"]["de"] == "2026-11-10T00:00:00-05:00"


@pytest.mark.parametrize("nome", ["Nao/Existe", "", "../etc"])
def test_fuso_que_nao_existe_sai_2_com_uma_frase(pasta, nome):
    fixture(pasta)
    r = roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria", fuso=nome)
    erro = r.stderr.decode("utf-8")
    assert r.returncode == 2 and r.stdout == b""
    assert erro.count("\n") == 1 and "--fuso" in erro and "Traceback" not in erro


# ---------------------------------------------------------------- the default folder


def _projetos(tmp_path: Path) -> Path:
    return tmp_path / "config" / "projects"  # the conftest's CLAUDE_CONFIG_DIR


def test_variavel_ganha_da_sessao_encontrada(pasta, tmp_path):
    fixture(pasta)
    sessao(_projetos(tmp_path) / "-outro", "medindo").humano("2026-11-11T09:00")
    r = roda("--abre", ROTINA, *JANELA, "--sessao-propria", "medindo",
             "--desde", "2026-11-11T09:15")
    regua = json.loads(r.stdout)["regua"]
    assert regua["regra_da_pasta"] == "variavel" and regua["fonte"] == str(pasta.resolve())


def test_pasta_da_sessao_propria_vem_depois_da_variavel(pasta, tmp_path, monkeypatch):
    monkeypatch.delenv("IA_CODIGO_PROJETOS_DIR")
    dela = _projetos(tmp_path) / "-a-projeto"
    fixture(dela)
    (_projetos(tmp_path) / "-b-outro").mkdir()
    r = roda("--abre", ROTINA, *JANELA, "--sessao-propria", "claude:medindo",
             "--desde", "2026-11-11T09:15")
    dados = json.loads(r.stdout)
    assert dados["regua"]["regra_da_pasta"] == "sessao_propria"
    assert dados["regua"]["fonte"] == str(dela.resolve())
    assert len(dados["execucoes"]) == 2


def test_sessao_sem_arquivo_cai_na_pasta_atual(pasta, tmp_path, monkeypatch):
    monkeypatch.delenv("IA_CODIGO_PROJETOS_DIR")
    atual = tmp_path / "meu proj"
    atual.mkdir()
    dela = _projetos(tmp_path) / tr.codifica_raiz(atual.resolve())
    fixture(dela)
    (dela / "medindo.jsonl").rename(dela / "outra.jsonl")  # the own session is nowhere
    r = roda("--abre", ROTINA, *JANELA, "--sessao-propria", "medindo",
             "--desde", "2026-11-11T09:15", cwd=atual)
    regua = json.loads(r.stdout)["regua"]
    assert regua["regra_da_pasta"] == "pasta_atual" and regua["fonte"] == str(dela.resolve())
    sem = json.loads(roda("--abre", ROTINA, *JANELA, "--sem-sessao-propria", cwd=atual).stdout)
    assert sem["regua"]["regra_da_pasta"] == "pasta_atual"


def test_nada_existe_sai_2(pasta, tmp_path, monkeypatch):
    monkeypatch.delenv("IA_CODIGO_PROJETOS_DIR")
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    r = roda("--abre", ROTINA, *JANELA, "--sessao-propria", "medindo",
             "--desde", "2026-11-11T09:15", cwd=vazia)
    erro = r.stderr.decode("utf-8")
    assert r.returncode == 2 and r.stdout == b""
    assert "não existe" in erro and "Traceback" not in erro


def test_pasta_dada_tem_regra_pasta(pasta, tmp_path):
    fixture(pasta)
    r = roda("--pasta", str(pasta), "--abre", ROTINA, *JANELA, "--sem-sessao-propria")
    regua = json.loads(r.stdout)["regua"]
    assert regua["regra_da_pasta"] == "pasta" and regua["fonte"] == str(pasta.resolve())
