"""execucoes.py — the one verb of harness-review: the runs of one routine and what each cost.

Functions:

- ``execucoes(leitura, abre, fecha, resposta, acoes, prazo_uso_h=24) -> dict``
  a pure function over a ``transcritos.Leitura``. Patterns are strings:
  ``abre`` is ``skill:<name>``, ``texto:<regex>`` or ``comando:<regex>``; ``fecha`` is None,
  ``texto:<regex>`` or ``comando:<regex>``; ``resposta`` is None or a regex over opener text;
  ``acoes`` is a list of ``comando:<regex>``. A bad prefix, an empty skill name or a regex
  that does not compile raises ``ValueError`` with a plain Portuguese sentence.

Output: ``{"execucoes": [...], "totais": {...}, "regua": {...}}``. Each run carries ``sessao``,
``agente`` (None in a main file), ``inicio``/``fim`` (local time, ``transcritos.hora_local``),
``sinais`` (any of ``corta_janela``, ``sessao_comecou_antes``, ``atribuido_por_hora``,
``acordar_compartilhado``), ``estreito``, ``largo``
and ``acordar`` (each ``entrada``, ``gravados``, ``relidos``, ``escritos``, ``contexto``,
``chamadas``), ``ajudantes`` (per resolved type: ``quantos``, ``chamadas``, the usage split,
``modelos``, and ``acordar`` — their first calls, kept apart from the main ``acordar``),
``comandos`` (``por_desfecho`` counts and ``mais_de_uma_tentativa``), ``respondido`` /
``minutos_ate_resposta``, ``agido`` / ``minutos_ate_acao`` and ``uso_indefinido``.
``totais`` has ``n`` and, for ``estreito`` and ``largo``, ``n``/``mediana``/``min``/``max``
over ONE number per run: ``contexto + escritos`` (every token the calls read or wrote);
``acordar`` has the same four over one number per FILE that holds a run (that file's first
call, counted once however many runs share it), so its ``n`` is the number of files.
``regua`` is the reading's ruler with ``padroes`` filled with the patterns given and
``padroes_casados`` with how many openers or commands each matched anywhere in the reading
(``abre``, ``fecha`` or None, ``resposta`` or None, ``acao`` one count per pattern); a
``resposta`` or ``acao`` that matched 0 adds an ``avisos`` line (a wrong pattern, not "no use";
it is not ``formato_mudou``).

Rules (each has a test in tests/test_execucoes.py):

1. Opening: ``skill:`` is a ``Skill`` tool_use with that ``input.skill`` or a ``comando``
   opener naming it (a Skill call of the same name in the same human turn as that typed
   command is the same opening, not a second run); ``texto:`` any opener, main or sub-agent
   file; ``comando:`` a Bash tool_use whose whole command matches.
2. A run belongs to the window by its opening's timestamp only.
3. End without ``fecha``: the event before the next human opener (``humano`` or a typed
   ``comando``) or the next opening in the same file, else the file's last event. A ``meta``
   opener never ends a run.
4. With ``fecha``: the run stretches to the call after the last ``fecha`` match before the
   next opening in the same file (never shorter than rule 3).
5. ``estreito``: the opening call (for an opener, the first call after it) plus each ``fecha``
   match's call (for a ``texto:`` match, the first call after it) and its next call.
   ``largo``: every call of the run in its file plus every sub-agent whose ``toolUseId`` is a
   tool_use of the run or of a sub-agent already counted (nested), plus a teammate without
   ``toolUseId`` of the same session that starts inside the run (``atribuido_por_hora``).
   ``acordar``: the first call of the run's file (``sessao_comecou_antes`` when it is before
   the window's start; ``acordar_compartilhado`` when the run's opening is not the first
   opener or call of its file, so that wake is shared with what came before and is not this
   run's own cost).
6. ``comandos``: the run's own Bash calls by outcome (``sem_resultado`` when no result was
   read); ``mais_de_uma_tentativa`` when the same command text failed (any outcome but ``ok``
   or ``saida_0``) and later ended ``ok`` or ``saida_0`` inside the run. A hook denial counts
   in its own bucket.
7. Use, scoped to the run's own session: ``respondido`` looks at the openers of the run's
   own file (a main file is the session's main file) later than the run's opening — a chat
   channel plugin's reply arrives as a ``meta`` opener, which stays inside the run by rule 3 —
   never a system notice (``AVISOS_DO_SISTEMA``) nor a sub-agent's first prompt; ``agido`` looks
   at the Bash calls of the run's session (main file and its sub-agent files) strictly after
   the run's last event, so the routine's own commands never count as his action. Both stop
   before the next opening of the same ``--abre`` in the same file and before the opening
   plus ``prazo_uso_h`` (from the opening, not the end: a reply inside the run moves the end,
   and a run in an always-on session can reach the file's end). ``minutos_ate_resposta`` is
   counted from the run's opening, ``minutos_ate_acao`` from the run's end. Without
   ``resposta`` and ``acoes`` every run is ``uso_indefinido`` and both are None, never true.
8. Privacy: only ids, resolved types, model names, counts, outcomes and timestamps leave;
   no opener text, command, path or result text.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import transcritos as tr

_CAMPOS = ("entrada", "gravados", "relidos", "escritos", "contexto")


@dataclass
class _Padrao:
    tipo: str  # "skill" | "texto" | "comando"
    nome: str | None
    rx: re.Pattern[str] | None


def _compila(texto: str, onde: str) -> re.Pattern[str]:
    try:
        return re.compile(texto)
    except re.error as erro:
        raise ValueError(f"o padrão de {onde} não é uma expressão regular válida "
                         f"({texto!r}: {erro}).") from None


def _padrao(texto: str, onde: str, tipos: tuple[str, ...]) -> _Padrao:
    prefixo, sep, resto = texto.partition(":")
    if not sep or prefixo not in tipos:
        aceitos = ", ".join(f"{t}:…" for t in tipos)
        raise ValueError(f"o padrão de {onde} precisa começar com {aceitos} "
                         f"(veio {texto!r}).")
    if prefixo == "skill":
        nome = resto.strip().lstrip("/")
        if not nome:
            raise ValueError(f"o padrão de {onde} diz skill: mas não diz qual skill.")
        return _Padrao("skill", nome, None)
    return _Padrao(prefixo, None, _compila(resto, onde))


def _soma(chamadas: list[tr.Chamada]) -> dict[str, int]:
    total = dict.fromkeys(_CAMPOS, 0)
    for c in chamadas:
        for k in _CAMPOS:
            total[k] += c.uso[k]
    total["chamadas"] = len(chamadas)
    return total


def _humano(ev: Any) -> bool:
    return isinstance(ev, tr.Abertura) and ev.origem in ("humano", "comando")


def _bash(ch: tr.Chamada) -> list[tr.ToolUse]:
    return [t for t in ch.tool_uses
            if t.nome == "Bash" and isinstance(t.input.get("command"), str)]


def _casa(p: _Padrao, ev: Any) -> bool:
    if p.tipo == "skill":
        if isinstance(ev, tr.Abertura):
            return ev.origem == "comando" and ev.comando == p.nome
        return any(t.nome == "Skill" and t.input.get("skill") == p.nome for t in ev.tool_uses)
    assert p.rx is not None
    if p.tipo == "texto":
        return isinstance(ev, tr.Abertura) and p.rx.search(ev.texto) is not None
    return isinstance(ev, tr.Chamada) and any(
        p.rx.search(t.input["command"]) for t in _bash(ev))


def _conta(p: _Padrao, leitura: tr.Leitura) -> int:
    """How many openers (``texto:``, a typed ``/name``) or commands (``comando:``, a Skill call)
    the pattern matches anywhere in the reading."""
    if p.tipo == "skill":
        return (sum(1 for ab in leitura.aberturas
                    if ab.origem == "comando" and ab.comando == p.nome)
                + sum(1 for c in leitura.chamadas for t in c.tool_uses
                      if t.nome == "Skill" and t.input.get("skill") == p.nome))
    assert p.rx is not None
    if p.tipo == "texto":
        return sum(1 for ab in leitura.aberturas if p.rx.search(ab.texto))
    return sum(1 for c in leitura.chamadas for t in _bash(c) if p.rx.search(t.input["command"]))


def _aberturas_do_arquivo(eventos: list[Any], p: _Padrao) -> list[int]:
    idx: list[int] = []
    for i, ev in enumerate(eventos):
        if not _casa(p, ev):
            continue
        if (p.tipo == "skill" and isinstance(ev, tr.Chamada) and idx
                and isinstance(eventos[idx[-1]], tr.Abertura)
                and not any(_humano(e) for e in eventos[idx[-1] + 1:i])):
            continue  # the Skill call answering the typed /name: same opening
        idx.append(i)
    return idx


def _proxima_chamada(eventos: list[Any], depois_de: int, antes_de: int) -> int | None:
    for j in range(depois_de + 1, antes_de):
        if isinstance(eventos[j], tr.Chamada):
            return j
    return None


@dataclass
class _Corrida:
    arquivo: tr.Arquivo
    eventos: list[Any]
    inicio: int
    fim: int
    estreito: list[int]


def _corridas(a: tr.Arquivo, abre: _Padrao, fecha: _Padrao | None) -> list[_Corrida]:
    ev = a.eventos
    aberturas = _aberturas_do_arquivo(ev, abre)
    saida = []
    for k, i in enumerate(aberturas):
        limite = aberturas[k + 1] if k + 1 < len(aberturas) else len(ev)
        fim = limite - 1
        for j in range(i + 1, limite):
            if _humano(ev[j]):
                fim = j - 1
                break
        primeira = i if isinstance(ev[i], tr.Chamada) else _proxima_chamada(ev, i, limite)
        estreito = [primeira] if primeira is not None else []
        if fecha is not None:
            casos = [j for j in range(i, limite) if _casa(fecha, ev[j])]
            for j in casos:
                base = j if isinstance(ev[j], tr.Chamada) else _proxima_chamada(ev, j, limite)
                if base is None:
                    continue
                estreito.append(base)
                seguinte = _proxima_chamada(ev, base, limite)
                if seguinte is not None:
                    estreito.append(seguinte)
            if casos:
                ultimo = casos[-1]
                seguinte = _proxima_chamada(ev, ultimo, limite)
                fim = max(fim, seguinte if seguinte is not None else ultimo)
        saida.append(_Corrida(a, ev, i, fim, sorted(set(estreito))))
    return saida


def _mediana(valores: list[int]) -> dict[str, Any]:
    if not valores:
        return {"n": 0, "mediana": None, "min": None, "max": None}
    return {"n": len(valores), "mediana": statistics.median(valores),
            "min": min(valores), "max": max(valores)}


def _minutos(de: datetime, ate: datetime) -> float:
    return round((ate - de).total_seconds() / 60, 1)


def execucoes(leitura: tr.Leitura, abre: str, fecha: str | None, resposta: str | None,
              acoes: list[str], prazo_uso_h: float = 24) -> dict[str, Any]:
    p_abre = _padrao(abre, "--abre", ("skill", "texto", "comando"))
    p_fecha = _padrao(fecha, "--fecha", ("texto", "comando")) if fecha is not None else None
    rx_resposta = _compila(resposta, "--resposta") if resposta is not None else None
    p_acoes = [_padrao(x, "--acao", ("comando",)) for x in acoes]
    rx_acoes = [p.rx for p in p_acoes if p.rx is not None]
    janela_de = datetime.fromisoformat(leitura.regua["janela"]["de"])
    janela_ate = datetime.fromisoformat(leitura.regua["janela"]["ate"])
    prazo = timedelta(hours=prazo_uso_h)

    chamadas_por_arquivo: dict[str, list[tr.Chamada]] = {}
    for c in leitura.chamadas:
        chamadas_por_arquivo.setdefault(c.arquivo, []).append(c)
    por_tool_use = {aj.tool_use_id: aj for aj in leitura.ajudantes if aj.tool_use_id}

    # replies: openers of each file, never a system notice nor a sub-agent's first prompt
    respostas_por_arquivo: dict[str, list[tr.Abertura]] = {}
    for a in leitura.arquivos:
        dele = [ev for ev in a.eventos if isinstance(ev, tr.Abertura)]
        if not a.principal:
            dele = dele[1:]
        respostas_por_arquivo[a.nome] = sorted(
            (ab for ab in dele if ab.timestamp is not None
             and not ab.texto.lstrip().startswith(tr.AVISOS_DO_SISTEMA)),
            key=lambda ab: ab.timestamp)
    # actions: Bash commands of each session (main file and its sub-agent files)
    comandos_por_sessao: dict[str, list[tuple[datetime, str]]] = {}
    for c in leitura.chamadas:
        if c.timestamp is not None:
            comandos_por_sessao.setdefault(c.sessao, []).extend(
                (c.timestamp, t.input["command"]) for t in _bash(c))
    for lista in comandos_por_sessao.values():
        lista.sort(key=lambda x: x[0])

    todas = [r for a in leitura.arquivos for r in _corridas(a, p_abre, p_fecha)
             if r.eventos[r.inicio].timestamp is not None]
    inicios_por_arquivo: dict[str, list[datetime]] = {}
    for r in todas:
        inicios_por_arquivo.setdefault(r.arquivo.nome, []).append(r.eventos[r.inicio].timestamp)
    for lista_ts in inicios_por_arquivo.values():
        lista_ts.sort()

    saida: list[dict[str, Any]] = []
    arquivos_das_corridas: dict[str, None] = {}  # ordered set
    for r in sorted(todas, key=lambda r: r.eventos[r.inicio].timestamp):
        inicio = r.eventos[r.inicio].timestamp
        if not (janela_de <= inicio <= janela_ate):
            continue
        trecho = r.eventos[r.inicio:r.fim + 1]
        fim = max((e.timestamp for e in trecho if e.timestamp is not None), default=inicio)
        proprias = [e for e in trecho if isinstance(e, tr.Chamada)]
        sinais: list[str] = []
        if fim > janela_ate:
            sinais.append("corta_janela")

        # sub-agents of the run, nested ones included
        ids = {t.id for c in proprias for t in c.tool_uses}
        incluidos: list[tr.Ajudante] = []
        fila = list(ids)
        vistos: set[str] = set()
        while fila:
            tid = fila.pop()
            aj = por_tool_use.get(tid)
            if aj is None or aj.arquivo in vistos or aj.arquivo == r.arquivo.nome:
                continue
            vistos.add(aj.arquivo)
            incluidos.append(aj)
            fila.extend(t.id for c in chamadas_por_arquivo.get(aj.arquivo, [])
                        for t in c.tool_uses)
        por_hora = [aj for aj in leitura.ajudantes
                    if aj.equipe and aj.tool_use_id is None and aj.sessao == r.arquivo.sessao
                    and aj.arquivo != r.arquivo.nome and aj.arquivo not in vistos
                    and aj.primeiro_timestamp is not None
                    and inicio <= aj.primeiro_timestamp <= fim]
        if por_hora:
            sinais.append("atribuido_por_hora")
            incluidos += por_hora

        ajudantes: dict[str, dict[str, Any]] = {}
        chamadas_aj: list[tr.Chamada] = []
        for aj in incluidos:
            dele = chamadas_por_arquivo.get(aj.arquivo, [])
            chamadas_aj += dele
            g = ajudantes.setdefault(aj.tipo, {"quantos": 0, "_ch": [], "_ac": [],
                                               "modelos": set()})
            g["quantos"] += 1
            g["_ch"] += dele
            g["_ac"] += dele[:1]
            g["modelos"].update(m for m in [aj.modelo, *(c.modelo for c in dele)] if m)
        ajudantes_saida = {}
        for tipo in sorted(ajudantes):
            g = ajudantes[tipo]
            linha = {"quantos": g["quantos"], **_soma(g["_ch"]),
                     "modelos": sorted(g["modelos"]), "acordar": _soma(g["_ac"])}
            ajudantes_saida[tipo] = linha

        primeiras = chamadas_por_arquivo.get(r.arquivo.nome, [])[:1]
        if primeiras and primeiras[0].timestamp is not None \
                and primeiras[0].timestamp < janela_de:
            sinais.append("sessao_comecou_antes")
        if r.inicio > 0:
            sinais.append("acordar_compartilhado")

        # commands of the run's own calls
        por_desfecho: dict[str, int] = {}
        falhou: set[str] = set()
        repetiu = False
        for c in proprias:
            for t in _bash(c):
                d = leitura.resultados.get(t.id, "sem_resultado")
                por_desfecho[d] = por_desfecho.get(d, 0) + 1
                cmd = t.input["command"]
                if d in ("ok", "saida_0"):
                    repetiu = repetiu or cmd in falhou
                else:
                    falhou.add(cmd)

        # was the result used (rule 7)
        depois = [s for s in inicios_por_arquivo[r.arquivo.nome] if s > inicio]
        limite = min([inicio + prazo, *depois[:1]])
        respondido = minutos_r = agido = minutos_a = None
        if rx_resposta is not None:
            respondido = False
            for ab in respostas_por_arquivo.get(r.arquivo.nome, []):
                if inicio < ab.timestamp < limite and rx_resposta.search(ab.texto):
                    respondido, minutos_r = True, _minutos(inicio, ab.timestamp)
                    break
        if rx_acoes:
            agido = False
            for ts, cmd in comandos_por_sessao.get(r.arquivo.sessao, []):
                if fim < ts < limite and any(rx.search(cmd) for rx in rx_acoes):
                    agido, minutos_a = True, _minutos(fim, ts)
                    break

        saida.append({
            "sessao": r.arquivo.sessao,
            "agente": r.arquivo.agente,
            "inicio": tr.hora_local(inicio),
            "fim": tr.hora_local(fim),
            "sinais": sinais,
            "estreito": _soma([r.eventos[j] for j in r.estreito]),
            "largo": _soma(proprias + chamadas_aj),
            "acordar": _soma(primeiras),
            "ajudantes": ajudantes_saida,
            "comandos": {"por_desfecho": por_desfecho, "mais_de_uma_tentativa": repetiu},
            "respondido": respondido,
            "minutos_ate_resposta": minutos_r,
            "agido": agido,
            "minutos_ate_acao": minutos_a,
            "uso_indefinido": rx_resposta is None and not rx_acoes,
        })
        arquivos_das_corridas.setdefault(r.arquivo.nome, None)

    def numero(x: dict[str, int]) -> int:
        return x["contexto"] + x["escritos"]

    totais: dict[str, Any] = {"n": len(saida), "numero": "contexto + escritos"}
    for k in ("estreito", "largo"):
        totais[k] = _mediana([numero(e[k]) for e in saida])
    # one wake per file: runs of one always-on session share its first call
    totais["acordar"] = _mediana([numero(_soma(chamadas_por_arquivo[nome][:1]))
                                  for nome in arquivos_das_corridas
                                  if chamadas_por_arquivo.get(nome)])

    regua = dict(leitura.regua)
    regua["avisos"] = list(leitura.regua["avisos"])
    regua["padroes"] = {"abre": abre, "fecha": fecha, "resposta": resposta,
                        "acao": list(acoes)}
    casados: dict[str, Any] = {
        "abre": _conta(p_abre, leitura),
        "fecha": _conta(p_fecha, leitura) if p_fecha is not None else None,
        "resposta": (sum(1 for ab in leitura.aberturas if rx_resposta.search(ab.texto))
                     if rx_resposta is not None else None),
        "acao": [_conta(p, leitura) for p in p_acoes],
    }
    regua["padroes_casados"] = casados
    if casados["resposta"] == 0:
        regua["avisos"].append("o padrão de resposta não casou com nada na leitura: confira o "
                               "padrão antes de dizer que não houve uso")
    for texto, n in zip(acoes, casados["acao"]):
        if n == 0:
            regua["avisos"].append(f"o padrão de ação {texto!r} não casou com nada na leitura: "
                                   "confira o padrão antes de dizer que não houve uso")
    return {"execucoes": saida, "totais": totais, "regua": regua}
