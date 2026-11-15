"""The absolutes of ia-vira-codigo, swept rather than sampled.

(a) Privacy (contract rule 11): one full fixture plants ``SENTINELA-PRIVADA`` everywhere
    ``fabrica.py`` plants it (message text, tool inputs, tool results, a meta's name and
    description, a teammate's team and own name); the verb runs with every ``--abre`` form, with
    and without each ``--fecha`` form, with ``--resposta``, several ``--acao``,
    ``--exclui-sessao`` and both own-session forms, in-process and through the CLI (exit 0 and
    exit 2). No output byte, stdout or stderr carries the sentinel. The checker looks for the
    prefix ``SENTINELA`` so a truncated copy is caught too; test names avoid that word because
    pytest names ``tmp_path`` after the test and the ruler echoes the folder. The patterns are
    echoed by design, so none of them contains the sentinel (asserted).
(b) Read-only and never wakes a model: an AST walk of ``transcritos.py``, ``execucoes.py`` and
    ``mede.py`` finds no file write (``open`` with a w/a/x/+ mode, positional or ``mode=``, or a
    mode it cannot read; ``write_text``/``write_bytes``/``unlink``/``rename``/``replace``/
    ``rmtree``/``mkdir``/``touch`` and their ``os`` twins), no network or model import
    (``socket``, ``urllib``, ``http``, ``requests``, ``anthropic``) and no way to start a process
    (``subprocess``, ``multiprocessing``, ``os.system``/``popen``/``exec*``/``spawn*``/``fork``),
    nor a dynamic import that would dodge the walk. A tool that is allowed to spawn processes
    would also need a PATH trap; here no process spawn is allowed at all, so no program on PATH
    (a fake ``claude``, ``node``, ``tmux``) can ever be reached and a trap would test a door that
    cannot exist. The CLI tests run the absolute ``sys.executable``.
(c) Each ruler both ways: one planted bad snippet per forbidden family is caught, look-alikes
    the modules really use (``datetime.replace``, ``str.replace``, ``Path.open("r")``,
    ``sys.stdout.buffer.write``) are not, and the three real modules are clean.
"""
from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import execucoes as ex
import pytest
import transcritos as tr
from fabrica import FUSO_TESTE, SENTINELA, ajudante, sessao, tu, uso

PLUGIN = Path(__file__).resolve().parents[1] / "skills" / "harness-review" / "reader"
MEDE = PLUGIN / "mede.py"
MODULOS = ("transcritos.py", "execucoes.py", "mede.py")
PROCURA = b"SENTINELA"  # the sentinel's prefix: a cut copy is a leak too

ABRE = {
    "skill": "skill:rotina-x",
    "texto": r"texto:^\[routine\] read",
    "comando": r"comando:tracker\.py done",
}
FECHA = {"sem": None, "texto": r"texto:source=.chat.",
         "comando": r"comando:EXIT=\$\?"}
RESPOSTA = r'source="chat"'
ACOES = [r"comando:tracker\.py done", r"comando:tracker\.py offered"]
PROPRIA = {"sem": None, "com": ("medindo", "2026-11-11T09:15")}


def vazamentos(**saidas: bytes | str) -> list[str]:
    """The names of the outputs that carry the sentinel (or a cut copy of it)."""
    return [nome for nome, s in saidas.items()
            if PROCURA in (s.encode("utf-8") if isinstance(s, str) else s)]


# ---------------------------------------------------------------- the full fixture


def mundo(pasta: Path) -> None:
    S = SENTINELA
    s = sessao(pasta, "s1")
    s.humano("2026-11-10T10:00")
    s.comando("2026-11-10T10:00:10", "rotina-x")
    s.assistente("2026-11-10T10:00:20", "r1", uso(entrada=3, relidos=50, escritos=5),
                 tool_uses=[tu("sk1", "Skill", skill="rotina-x", args=f"faz {S}")])
    s.resultado("2026-11-10T10:00:30", "sk1")
    repetido = f"tracker.py done 3 {S}"
    s.assistente("2026-11-10T10:01", "r2", uso(escritos=7), tool_uses=[
        tu("b-err", command=repetido, description=f"d {S}"),
        tu("b-code", command=f"ls /x/{S}"),
        tu("b-eco", command=f"false {S}; EXIT=$?; echo EXIT=$EXIT"),
        tu("b-hook", command=f"rm -rf /x/{S}"),
        tu("b-int", command=f"sleep 99 {S}"),
        tu("ler", "Read", file_path=f"/x/{S}.md"),
    ])
    s.resultado("2026-11-10T10:01:10", "b-err", f"falhou {S}", is_error=True)
    s.resultado("2026-11-10T10:01:11", "b-code", f"Exit code 1\n{S}", is_error=True)
    s.resultado("2026-11-10T10:01:12", "b-eco", f"{S}\nEXIT=3")
    s.resultado("2026-11-10T10:01:13", "b-hook", f"PreToolUse:Bash hook error: {S}",
                is_error=True)
    s.resultado("2026-11-10T10:01:14", "b-int", S,
                tool_use_result={"interrupted": True, "stdout": S})
    s.resultado("2026-11-10T10:01:15", "ler", f"conteudo {S}", blocos=True)
    s.assistente("2026-11-10T10:02", "r3", tool_uses=[
        tu("b-ok", command=repetido),
        tu("ag1", "Agent", subagent_type="Explore", prompt=f"p {S}", description=f"d {S}"),
    ])
    s.resultado("2026-11-10T10:02:01", "b-ok")
    s.resultado("2026-11-10T10:04:50", "ag1", f"relatorio {S}", blocos=True)
    s.meta("2026-11-10T10:05", f"[routine] read {S}")
    s.assistente("2026-11-10T10:05:30", None)  # no requestId, no id: keyed by file and uuid
    s.meta("2026-11-10T10:06", f'<channel source="chat">ok {S}</channel>')
    s.assistente("2026-11-10T10:06:30", "r4")
    s.interrompe("2026-11-10T10:07")
    s.compacta("2026-11-10T10:08")
    s.api_request_blob("2026-11-10T10:08:30")
    s.tipo("2026-11-10T10:08:40", "tipo-novo")
    s.linha_quebrada()
    s.humano("2026-11-10T11:00", f"outra coisa {S}", blocos=True)
    s.assistente("2026-11-10T11:01", "r5", tool_uses=[
        tu("b-acao", command=f"tracker.py offered {S}")])
    s.resultado("2026-11-10T11:01:30", "b-acao")

    a = ajudante(pasta, "s1", "a1b2c3", meta={"toolUseId": "ag1", "agentType": f"x {S}"})
    a.primeiro_pedido("2026-11-10T10:02:10")
    a.assistente("2026-11-10T10:02:20", "ra1", tool_uses=[
        tu("ba1"), tu("ag2", "Agent", subagent_type="general-purpose", prompt=f"p {S}")])
    a.resultado("2026-11-10T10:02:30", "ba1", f"PreToolUse:Bash denied {S}", is_error=True)
    a.resultado("2026-11-10T10:02:40", "ag2", f"r {S}")
    n = ajudante(pasta, "s1", "n1", meta={"toolUseId": "ag2", "parentAgentId": "a1b2c3"})
    n.primeiro_pedido("2026-11-10T10:02:35")
    n.assistente("2026-11-10T10:02:36", "rn1", tool_uses=[tu("bn1")])
    n.resultado("2026-11-10T10:02:37", "bn1")
    t = ajudante(pasta, "s1", "t1", meta={"teamName": f"time {S}",
                                          "spawnedAgentType": "pesquisador",
                                          "agentType": f"colega {S}"})
    t.primeiro_pedido("2026-11-10T10:03").assistente("2026-11-10T10:03:10", "rt1",
                                                      modelo="claude-sonnet-5")
    t2 = ajudante(pasta, "s1", "t2", meta={"teamName": f"time {S}"})
    t2.primeiro_pedido("2026-11-10T10:04").assistente("2026-11-10T10:04:10", "rt2")
    sem_meta = ajudante(pasta, "s1", "aExplore-abcdef12", com_meta=False)
    sem_meta.primeiro_pedido("2026-11-10T10:04:20").assistente("2026-11-10T10:04:30", "rx1")

    s2 = sessao(pasta, "s2")
    s2.meta("2026-11-11T08:00", f"[routine] read {S}")
    s2.comando("2026-11-11T08:00:10", "rotina-x")
    s2.assistente("2026-11-11T08:00:20", "r6", tool_uses=[
        tu("sk2", "Skill", skill="rotina-x"), tu("b6", command=f"tracker.py done 4 {S}")])
    s2.resultado("2026-11-11T08:00:30", "b6")
    q = ajudante(pasta, "s2", "q1", com_meta=False)
    q.primeiro_pedido("2026-11-11T08:01").assistente("2026-11-11T08:01:10", "rq1")
    (pasta / "s2" / "subagents" / "agent-q1.meta.json").write_text(
        '{"name": "' + S, encoding="utf-8")  # an unreadable meta

    m = sessao(pasta, "medindo")
    m.humano("2026-11-11T09:00")
    m.meta("2026-11-11T09:30", f"[routine] read {S}")
    m.assistente("2026-11-11T09:31", "r7", tool_uses=[
        tu("sk3", "Skill", skill="rotina-x"), tu("b7", command=f"tracker.py done 5 {S}")])

    f = sessao(pasta, "fora")
    f.meta("2026-11-11T10:00", f"[routine] read {S}")
    f.assistente("2026-11-11T10:01", "r8", tool_uses=[
        tu("b8", command=f"tracker.py done 6 {S}")])


def combinacoes() -> list[tuple[str, str, str]]:
    return [(a, f, p) for a in ABRE for f in FECHA for p in PROPRIA]


def test_padroes_nao_carregam_o_marcador():
    padroes = [*ABRE.values(), *(v for v in FECHA.values() if v), RESPOSTA, *ACOES]
    assert vazamentos(**{f"p{i}": p for i, p in enumerate(padroes)}) == []


def _em_processo(pasta: Path, abre: str, fecha: str | None, propria: str,
                 resposta: str | None = RESPOSTA, acoes: list[str] | None = None
                 ) -> dict:
    p = PROPRIA[propria]
    leitura = tr.ler(pasta, tr.para_utc("2026-11-10"),
                     tr.para_utc("2026-11-12", fim_do_dia=True),
                     None if p is None else (p[0], tr.para_utc(p[1])), ["fora"])
    return ex.execucoes(leitura, ABRE[abre], FECHA[fecha], resposta,
                        ACOES if acoes is None else acoes)


def test_a_fixture_exercita_tudo(pasta):
    """Guards the sweep against being vacuous: every outcome, every type source, every aviso."""
    mundo(pasta)
    saida = _em_processo(pasta, "skill", "sem", "sem")
    primeira = saida["execucoes"][0]
    assert primeira["sessao"] == "s1"
    assert set(primeira["comandos"]["por_desfecho"]) == {
        "ok", "erro", "saida_1", "saida_3", "negado_por_gancho", "interrompido"}
    assert primeira["comandos"]["mais_de_uma_tentativa"] is True
    assert set(primeira["ajudantes"]) == {"Explore", "general-purpose", "pesquisador",
                                          "desconhecido"}
    assert "atribuido_por_hora" in primeira["sinais"]
    assert primeira["respondido"] is True and primeira["agido"] is True
    regua = saida["regua"]
    assert regua["linhas_ilegiveis"] and regua["tipos_desconhecidos"] == {"tipo-novo": 1}
    assert regua["formato_mudou"] is True and len(regua["avisos"]) >= 3
    assert regua["duplicadas_por_uuid"] == 0 and regua["excluidas"] == ["fora"]
    fontes = regua["tipo_de_ajudante_por_fonte"]
    for fonte in ("spawnedAgentType", "subagent_type_do_pai", "nome_do_arquivo",
                  "desconhecido"):
        assert fontes[fonte] >= 1, fonte
    com = _em_processo(pasta, "skill", "sem", "com")
    assert {e["sessao"] for e in saida["execucoes"]} >= {"s1", "s2", "medindo"}
    assert "medindo" not in {e["sessao"] for e in com["execucoes"]}


# ---------------------------------------------------------------- (a) privacy, in-process


@pytest.mark.parametrize("abre,fecha,propria", combinacoes())
def test_privacidade_em_processo(pasta, capsys, abre, fecha, propria):
    mundo(pasta)
    saida = _em_processo(pasta, abre, fecha, propria)
    assert saida["execucoes"], "the sweep must see at least one run"
    texto = json.dumps(saida, ensure_ascii=False, sort_keys=True, indent=2)
    sem_uso = json.dumps(_em_processo(pasta, abre, fecha, propria, resposta=None, acoes=[]),
                         ensure_ascii=False)
    lido = capsys.readouterr()
    assert vazamentos(saida=texto, sem_uso=sem_uso, out=lido.out, err=lido.err) == []


# ---------------------------------------------------------------- (a) privacy, CLI


def roda(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(MEDE), "execucoes", "--fuso", FUSO_TESTE,
                           *args],
                          capture_output=True, env=dict(os.environ), timeout=60)


def _args(abre: str, fecha: str, propria: str, forma_desde: str = "local") -> list[str]:
    args = ["--abre", ABRE[abre], "--de", "2026-11-10", "--ate", "2026-11-12",
            "--resposta", RESPOSTA, "--exclui-sessao", "fora", "--exclui-sessao", "nenhuma"]
    for acao in ACOES:
        args += ["--acao", acao]
    if FECHA[fecha] is not None:
        args += ["--fecha", FECHA[fecha]]
    if propria == "sem":
        return args + ["--sem-sessao-propria"]
    desde = "2026-11-11T09:15" if forma_desde == "local" else "2026-11-11T14:15:00+00:00"
    return args + ["--sessao-propria", "claude:medindo", "--desde", desde]


@pytest.mark.parametrize("abre,fecha,propria", combinacoes())
def test_privacidade_pela_linha_de_comando(pasta, abre, fecha, propria):
    mundo(pasta)
    r = roda(*_args(abre, fecha, propria))
    assert r.returncode == 0, r.stderr.decode("utf-8")
    assert json.loads(r.stdout)["execucoes"]
    assert vazamentos(stdout=r.stdout, stderr=r.stderr) == []


def test_privacidade_desde_iso_e_sem_uso(pasta):
    mundo(pasta)
    r = roda(*_args("skill", "texto", "com", forma_desde="iso"))
    so_abre = roda("--abre", ABRE["texto"], "--de", "2026-11-10", "--ate", "2026-11-12",
                   "--sem-sessao-propria")
    for x in (r, so_abre):
        assert x.returncode == 0 and json.loads(x.stdout)["execucoes"]
    assert vazamentos(a=r.stdout, b=r.stderr, c=so_abre.stdout, d=so_abre.stderr) == []


@pytest.mark.parametrize("troca", [
    ["--resposta", "["],
    ["--abre", "texto:("],
    ["--abre", "rotina"],
    ["--acao", "texto:x"],
    ["sem-forma"],
    ["--pasta", "ausente"],
])
def test_privacidade_na_saida_2(pasta, tmp_path, troca):
    mundo(pasta)
    args = _args("texto", "sem", "sem")
    if troca == ["sem-forma"]:
        args.remove("--sem-sessao-propria")
    elif troca == ["--pasta", "ausente"]:
        args += ["--pasta", str(tmp_path / "nao-existe")]
    else:
        args += troca  # argparse keeps the last value of a single flag
    r = roda(*args)
    assert r.returncode == 2 and r.stdout == b""
    assert r.stderr and b"Traceback" not in r.stderr
    assert vazamentos(stdout=r.stdout, stderr=r.stderr) == []


def test_o_verificador_pega_um_vazamento_plantado(pasta):
    mundo(pasta)
    saida = _em_processo(pasta, "skill", "comando", "sem")
    limpo = json.dumps(saida, ensure_ascii=False)
    assert vazamentos(saida=limpo) == []
    for planta in (
        lambda d: d["execucoes"][0].__setitem__("sessao", SENTINELA),
        lambda d: d["execucoes"][0]["ajudantes"].__setitem__(f"colega {SENTINELA}", {}),
        lambda d: d["regua"]["avisos"].append(f"... {SENTINELA[:12]}"),  # a cut copy
    ):
        sujo = copy.deepcopy(saida)
        planta(sujo)
        assert vazamentos(saida=json.dumps(sujo, ensure_ascii=False)) == ["saida"]
    assert vazamentos(ok=b"{}", err=f"erro {SENTINELA}".encode()) == ["err"]


# ---------------------------------------------------------------- (b) read-only, no model

_IMPORTS_PROIBIDOS = {"subprocess", "multiprocessing", "socket", "urllib", "http",
                      "requests", "anthropic", "importlib"}
_METODOS_PROIBIDOS = {"write_text", "write_bytes", "unlink", "rename", "rmtree", "mkdir",
                      "touch", "symlink_to", "hardlink_to"}
_OS_PROIBIDOS = {"system", "popen", "startfile", "fork", "forkpty", "remove", "unlink",
                 "rename", "renames", "replace", "rmdir", "removedirs", "mkdir", "makedirs",
                 "open", "truncate"}
_OS_PREFIXOS = ("exec", "spawn", "posix_spawn")
_NOMES_PROIBIDOS = {"__import__", "exec", "eval"}


def _os_proibido(nome: str) -> bool:
    return nome in _OS_PROIBIDOS or nome.startswith(_OS_PREFIXOS)


def _modo_escreve(chamada: ast.Call, posicao: int) -> str | None:
    """The violation for an open() call whose mode writes, or that it cannot read."""
    modo: ast.expr | None = next((k.value for k in chamada.keywords if k.arg == "mode"), None)
    if modo is None and len(chamada.args) > posicao:
        modo = chamada.args[posicao]
    if modo is None:
        return None
    if not (isinstance(modo, ast.Constant) and isinstance(modo.value, str)):
        return "open:modo-ilegivel"
    return f"open:{modo.value}" if set(modo.value) & set("wax+") else None


def _violacoes(fonte: str) -> list[str]:
    achados: list[str] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Import):
            achados += [f"import:{a.name}" for a in no.names
                        if a.name.split(".")[0] in _IMPORTS_PROIBIDOS]
        elif isinstance(no, ast.ImportFrom):
            raiz = (no.module or "").split(".")[0]
            if raiz in _IMPORTS_PROIBIDOS:
                achados.append(f"import:{no.module}")
            elif raiz == "os":
                achados += [f"os.{a.name}" for a in no.names if _os_proibido(a.name)]
        elif isinstance(no, ast.Call):
            fn = no.func
            if isinstance(fn, ast.Name):
                if fn.id == "open":
                    achados += [v for v in [_modo_escreve(no, 1)] if v]
                elif fn.id in _NOMES_PROIBIDOS:
                    achados.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                dono = fn.value.id if isinstance(fn.value, ast.Name) else None
                if dono == "os" and _os_proibido(fn.attr):
                    achados.append(f"os.{fn.attr}")
                elif fn.attr == "open":
                    # io.open/codecs.open take the mode second; Path.open takes it first
                    pos = 1 if dono in ("io", "codecs") else 0
                    achados += [v for v in [_modo_escreve(no, pos)] if v]
                elif fn.attr in _METODOS_PROIBIDOS:
                    achados.append(fn.attr)
                elif fn.attr == "replace" and len(no.args) == 1 and not no.keywords:
                    achados.append("replace")  # Path.replace(target); str/datetime differ
    return achados


@pytest.mark.parametrize("arquivo", MODULOS)
def test_nunca_escreve_nem_acorda_um_modelo(arquivo):
    assert _violacoes((PLUGIN / arquivo).read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------- (c) each ruler both ways


@pytest.mark.parametrize("ruim,esperado", [
    ("open(p, 'w')", "open:w"),
    ("open(p, 'a', encoding='utf-8')", "open:a"),
    ("open(p, mode='x')", "open:x"),
    ("open(p, 'r+')", "open:r+"),
    ("open(p, modo)", "open:modo-ilegivel"),
    ("io.open(p, 'wb')", "open:wb"),
    ("p.open('w')", "open:w"),
    ("p.open(mode='a')", "open:a"),
    ("p.write_text('x')", "write_text"),
    ("p.write_bytes(b'x')", "write_bytes"),
    ("p.unlink()", "unlink"),
    ("p.rename(q)", "rename"),
    ("p.replace(q)", "replace"),
    ("shutil.rmtree(p)", "rmtree"),
    ("p.mkdir(parents=True)", "mkdir"),
    ("p.touch()", "touch"),
    ("os.remove(p)", "os.remove"),
    ("os.makedirs(p)", "os.makedirs"),
    ("os.open(p, 1)", "os.open"),
    ("import subprocess", "import:subprocess"),
    ("from subprocess import run", "import:subprocess"),
    ("import multiprocessing", "import:multiprocessing"),
    ("import socket", "import:socket"),
    ("import urllib.request", "import:urllib.request"),
    ("from http import client", "import:http"),
    ("import requests", "import:requests"),
    ("import anthropic", "import:anthropic"),
    ("from anthropic import Anthropic", "import:anthropic"),
    ("import importlib", "import:importlib"),
    ("__import__('subprocess')", "__import__"),
    ("exec('x')", "exec"),
    ("os.system('claude')", "os.system"),
    ("os.popen('claude')", "os.popen"),
    ("os.execv('/bin/sh', [])", "os.execv"),
    ("os.spawnl(0, 'claude')", "os.spawnl"),
    ("os.posix_spawn('claude', [], {})", "os.posix_spawn"),
    ("os.fork()", "os.fork"),
    ("from os import system", "os.system"),
])
def test_regua_pega_o_trecho_ruim(ruim, esperado):
    assert esperado in _violacoes(ruim)


def test_regua_deixa_passar_o_que_os_modulos_usam():
    bom = (
        "import json, os, re, sys\n"
        "from pathlib import Path\n"
        "with open(p) as f: pass\n"
        "with open(p, 'r', encoding='utf-8') as f: pass\n"
        "with p.open('r', encoding='utf-8', errors='replace') as f: pass\n"
        "p.read_text(encoding='utf-8')\n"
        "dt.replace(tzinfo=FUSO)\n"
        "s.replace('a', 'b')\n"
        "os.environ.get('X')\n"
        "p.stat().st_mtime\n"
        "re.compile('x')\n"
        "sys.stdout.buffer.write(b'x')\n"
        "print('x', file=sys.stderr)\n"
    )
    assert _violacoes(bom) == []
