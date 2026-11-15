"""transcritos.py — the parsing core of harness-review: reads Claude Code transcripts by code
only and hands the verb typed records (calls, openers, sub-agents, tool outcomes) plus a ruler.

Portions re-implement rules from Anthropic's session-report plugin (Apache-2.0); see NOTICE.

Functions:

- ``pasta_padrao(sessao=None) -> (Path, regra)``  the project's transcripts folder and the rule
                          that picked it: ``$IA_CODIGO_PROJETOS_DIR`` (the whole folder,
                          ``variavel``); else, when ``sessao`` (the measuring session's id) is
                          given, the folder under ``<config>/projects/`` that holds
                          ``<sessao>.jsonl`` (``sessao_propria``); else
                          ``<config>/projects/<codifica_raiz(cwd)>`` (``pasta_atual``).
                          ``<config>`` is ``$CLAUDE_CONFIG_DIR``, else ``~/.claude``.
- ``codifica_raiz(p)``    a path to its folder name: every char outside [A-Za-z0-9] becomes "-"
                          (the rule Claude Code uses for its per-project folders).
- ``define_fuso(nome)``   the zone every local time is read and shown in: an IANA name, or
                          ``None`` for the machine's own rules (the default). Raises
                          ``ValueError`` with a plain Portuguese sentence for an unknown name.
- ``para_utc(texto, fim_do_dia=False)``  "AAAA-MM-DD[THH:MM]" in that zone to an aware UTC
                          datetime; with ``fim_do_dia`` a date-only text means 23:59:59.999.
                          Without a zone, the naive time goes through ``astimezone()`` (the
                          machine's rules); with one, through ``zoneinfo`` (fold=0). The two
                          differ by one hour only for a local time inside a DST gap.
- ``hora_local(dt)``      an aware datetime as ISO text in that zone.
- ``desfecho(texto, is_error, tool_use_result, comando)``  one tool result's outcome (rule 9).
- ``ler(pasta, de, ate, propria, excluidas, regra_da_pasta="pasta") -> Leitura``  the whole
  read. ``de``/``ate`` are aware datetimes (use ``para_utc``); ``propria`` is
  ``(session id, desde)`` for the session doing the measuring, or ``None`` only for
  ``--sem-sessao-propria``; ``excluidas`` are whole session ids to leave out (main file and its
  sub-agents); ``regra_da_pasta`` is echoed in the ruler (``pasta`` when the folder was given).
  Raises ``PastaAusente`` when the folder does not exist; an empty folder is a valid answer.

``Leitura`` fields: ``arquivos`` (each read file with its ordered ``eventos``: ``Chamada`` and
``Abertura`` by ``posicao``, the 1-based line number of their first line), ``sessoes``,
``ajudantes``, ``chamadas`` (file order), ``aberturas`` (file order), ``resultados`` (tool_use
id -> outcome string) and ``regua`` (the contract's ruler dict; ``padroes`` and
``padroes_casados`` are left empty for the verb to fill).

Guarantees (each has a test):

1. Main files (``<pasta>/*.jsonl``) are read before sub-agent files
   (``<pasta>/<session>/subagents/**/agent-*.jsonl``); main by first timestamp then name,
   sub-agents by first timestamp then name with a nested child after its parent.
2. An unreadable line is counted per file in ``linhas_ilegiveis`` and sets ``formato_mudou``;
   the rest of the file is still read. An unreadable LAST line with no trailing newline is a
   line still being written (any file, the measuring session's own above all): it is counted
   per file in ``linhas_em_escrita`` and does not set ``formato_mudou``.
3. A ``uuid`` already seen (in this or an earlier file) is skipped and counted.
4. A file is read whole when any entry of it is inside the window; a file with no entry in the
   window contributes nothing (not even to the dedupe). Files last modified before ``de`` are
   not opened (they cannot hold an entry in the window).
5. An API call is an ``assistant`` line with ``message.usage``; its key is ``requestId``, else a
   ``msg_0…`` ``message.id`` longer than 10 chars, else ``<file>:<uuid>``; deduped globally, the
   usage with the largest ``output_tokens`` kept, every ``tool_use`` block of the key kept.
6. Only ``user`` lines can be openers; every other type and ``isCompactSummary`` is never a turn.
7. An opener is a ``user`` line with text content, no tool result, not an interrupt marker;
   ``origem`` is ``comando`` (typed slash command), ``meta`` (``isMeta``, or text starting
   with one of ``AVISOS_DO_SISTEMA`` whatever ``isMeta`` says) or ``humano``.
8. Sub-agent type, first hit wins: customAgentType, spawnedAgentType, the parent Agent call's
   ``subagent_type`` (by the meta's ``toolUseId``), agentType, filename label, "desconhecido".
9. Tool outcome order: hook denial prefix, ``Exit code N``, trailing ``EXIT=N`` (only when the
   command has ``EXIT=$?``), ``interrupted``, then ``ok``/``erro`` by ``is_error``.
10. Commands are kept whole in ``ToolUse.input``.
11. Nothing here prints; the ruler carries no message text, command, path from a tool input,
    result text, nor a meta's ``name``/``description`` (those are never even stored).
12. The ruler says how it was read: ``fonte`` (the folder path), ``regra_da_pasta`` (which
    rule picked it: ``pasta``, ``variavel``, ``sessao_propria`` or ``pasta_atual``) and
    ``fuso`` (the zone's name, or ``"local"`` for the machine's rules).

Reads only: files are opened for reading, line by line, ``errors="replace"``. Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# The zone set by ``define_fuso``; ``None`` means the machine's own rules.
_FUSO: tzinfo | None = None
_NOME_DO_FUSO: str | None = None

# Frozen from a counts-only probe of the real folder on 15/11 (main and sub-agent files),
# plus ``summary`` named in the contract. Anything else lands in ``tipos_desconhecidos``.
TIPOS_CONHECIDOS = frozenset({
    "custom-title", "agent-name", "last-prompt", "mode", "permission-mode",
    "session-owner", "attachment", "system", "user", "file-history-snapshot",
    "api-request-shape", "api-request-blob", "api-request", "atis-latch", "tools-used",
    "assistant", "cost-state", "queue-operation", "file-history-delta", "ai-title",
    "artifact-comment-monitor", "artifact-autoreact-ledger", "bridge-session",
    "frame-link", "continued-in", "dev-mods", "launched", "started", "result", "summary",
})

# Closed list, frozen from real lines on 15/11: every "PreToolUse:" result had is_error true.
GANCHO_PREFIXOS: tuple[str, ...] = ("PreToolUse:",)

INTERRUPCAO = "[Request interrupted"

# Closed list, from a counts-only probe of real lines 07/11-15/11: a sub-agent completion
# notice is a user line without ``isMeta``; these openers are ``meta`` whatever ``isMeta`` says.
# ``<teammate-message`` (a lead's or colleague's message to a teammate) and
# ``<local-command-stdout`` (the printed output of a local slash command) added 15/11 from the
# reviewer's probe: both arrive without ``isMeta`` and are never the user's own turn.
AVISOS_DO_SISTEMA: tuple[str, ...] = (
    "<task-notification", "<teammate-message", "<local-command-stdout",
)

# The method's own names for the four usage fields; ``contexto`` is the sum of the first three.
CAMPOS_DE_USO: tuple[tuple[str, str], ...] = (
    ("entrada", "input_tokens"),
    ("gravados", "cache_creation_input_tokens"),
    ("relidos", "cache_read_input_tokens"),
    ("escritos", "output_tokens"),
)

FONTES_DE_TIPO: tuple[str, ...] = (
    "customAgentType", "spawnedAgentType", "subagent_type_do_pai", "agentType",
    "nome_do_arquivo", "desconhecido",
)

# analyze-sessions.mjs inferAgentTypeFromFilename: 'a' + label + '-' + hex. Anthropic's
# session-report plugin (Apache-2.0), skills/session-report/analyze-sessions.mjs at
# https://github.com/anthropics/claude-plugins-official/tree/main/plugins/session-report
_ROTULO = re.compile(r"^agent-a([a-zA-Z_][\w-]*?)-[0-9a-f]{6,}$")
_COMANDO = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>")
_EXIT_CODE = re.compile(r"^\s*(?:<error>\s*)?Exit code (-?\d+)")
_EXIT_ECO = re.compile(r"EXIT=(-?\d+)\s*(?:</error>)?\s*$")


class PastaAusente(FileNotFoundError):
    """The transcripts folder does not exist."""


@dataclass
class ToolUse:
    id: str
    nome: str
    input: dict[str, Any] = field(repr=False)


@dataclass
class Chamada:
    chave: str
    arquivo: str
    sessao: str
    agente: str | None
    timestamp: datetime | None
    posicao: int
    modelo: str | None
    uso: dict[str, int]
    tool_uses: list[ToolUse]


@dataclass
class Abertura:
    origem: str  # "humano" | "meta" | "comando"
    arquivo: str
    sessao: str
    agente: str | None
    timestamp: datetime | None
    posicao: int
    texto: str = field(repr=False)  # memory only, for pattern matching; never output
    comando: str | None = None  # slash command name without "/", when origem is comando


@dataclass
class Ajudante:
    agente: str
    sessao: str
    arquivo: str
    tipo: str
    fonte_do_tipo: str
    tool_use_id: str | None
    parent_agent_id: str | None
    modelo: str | None
    equipe: bool  # the meta has teamName (a teammate)
    primeiro_timestamp: datetime | None
    ultimo_timestamp: datetime | None


@dataclass
class Sessao:
    id: str
    arquivo: str
    primeiro_timestamp: datetime | None
    ultimo_timestamp: datetime | None


@dataclass
class Arquivo:
    nome: str  # path relative to the transcripts folder
    sessao: str
    agente: str | None  # None for a main file
    principal: bool
    primeiro_timestamp: datetime | None
    ultimo_timestamp: datetime | None
    eventos: list[Chamada | Abertura]


@dataclass
class Leitura:
    arquivos: list[Arquivo]
    sessoes: list[Sessao]
    ajudantes: list[Ajudante]
    chamadas: list[Chamada]
    aberturas: list[Abertura]
    resultados: dict[str, str]
    regua: dict[str, Any]


# ---------------------------------------------------------------- folder and time


def codifica_raiz(p: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(p))


def pasta_padrao(sessao: str | None = None) -> tuple[Path, str]:
    inteira = os.environ.get("IA_CODIGO_PROJETOS_DIR")
    if inteira:
        return Path(inteira), "variavel"
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    projetos = (Path(base) if base else Path.home() / ".claude") / "projects"
    if sessao and projetos.is_dir():
        for d in sorted(x for x in projetos.iterdir() if x.is_dir()):
            if (d / f"{sessao}.jsonl").is_file():
                return d, "sessao_propria"
    return projetos / codifica_raiz(Path.cwd()), "pasta_atual"


def define_fuso(nome: str | None) -> None:
    """Set the zone for ``para_utc``, ``hora_local`` and the ruler; ``None`` is the machine's."""
    global _FUSO, _NOME_DO_FUSO
    if nome is None:
        _FUSO = _NOME_DO_FUSO = None
        return
    try:
        fuso = ZoneInfo(nome)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"--fuso precisa de um nome de fuso IANA, como America/New_York "
                         f"(veio {nome!r}).") from None
    _FUSO, _NOME_DO_FUSO = fuso, nome


def para_utc(texto: str, fim_do_dia: bool = False) -> datetime:
    """'AAAA-MM-DD' or 'AAAA-MM-DDTHH:MM' read in the zone of ``define_fuso``, in UTC."""
    for formato in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            local = datetime.strptime(texto, formato)
        except ValueError:
            continue
        if formato == "%Y-%m-%d" and fim_do_dia:
            local = local + timedelta(days=1) - timedelta(milliseconds=1)
        if _FUSO is None:
            return local.astimezone(timezone.utc)  # naive: the machine's own rules
        return local.replace(tzinfo=_FUSO).astimezone(timezone.utc)
    raise ValueError(f"data fora do formato AAAA-MM-DD[THH:MM]: {texto!r}")


def hora_local(dt: datetime) -> str:
    return dt.astimezone(_FUSO).isoformat()  # astimezone(None) is the machine's zone


def _ts(valor: Any) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        dt = datetime.fromisoformat(valor)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- tool outcome (rule 9)


def _texto_de(conteudo: Any) -> str:
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return "\n".join(
            b["text"] for b in conteudo
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)
        )
    return ""


def desfecho(texto: str, is_error: bool, tool_use_result: Any, comando: str | None) -> str:
    """One tool result's outcome, rule 9 in order. ``tool_use_result`` may be a dict (its
    ``interrupted`` flag is read), a list of text blocks or a string (both used as the text
    when the result block carried none)."""
    if not texto and not isinstance(tool_use_result, dict):
        texto = _texto_de(tool_use_result)
    inicio = texto.lstrip()
    if inicio.startswith(GANCHO_PREFIXOS):
        return "negado_por_gancho"
    m = _EXIT_CODE.match(texto)
    if m:
        return f"saida_{m.group(1)}"
    if comando is not None and "EXIT=$?" in comando:
        m = _EXIT_ECO.search(texto)
        if m:
            return f"saida_{m.group(1)}"
    if isinstance(tool_use_result, dict) and tool_use_result.get("interrupted") is True:
        return "interrompido"
    return "erro" if is_error else "ok"


# ---------------------------------------------------------------- per-file reading


@dataclass
class _Candidato:
    caminho: Path
    nome: str
    sessao: str
    agente: str | None
    principal: bool
    primeiro: datetime | None
    meta: dict[str, Any] | None = None


@dataclass
class _Global:
    uuids: set[str] = field(default_factory=set)
    chamadas: dict[str, Chamada] = field(default_factory=dict)
    resultados_brutos: dict[str, tuple[str, bool, Any]] = field(default_factory=dict)
    duplicadas: int = 0
    linhas: int = 0
    ilegiveis: dict[str, int] = field(default_factory=dict)
    em_escrita: dict[str, int] = field(default_factory=dict)
    tipos: Counter[str] = field(default_factory=Counter)
    sem_chave: int = 0
    avisos: list[str] = field(default_factory=list)
    formato_mudou: bool = False


def _chave(e: dict[str, Any], msg: dict[str, Any], nome: str, linha: int) -> tuple[str, bool]:
    # analyze-sessions.mjs 303-308 (Anthropic's session-report plugin, Apache-2.0, see the
    # upstream path at _ROTULO): requestId, else a real msg_0 id, else file:uuid.
    req = e.get("requestId")
    if isinstance(req, str) and req:
        return req, True
    mid = msg.get("id")
    if isinstance(mid, str) and mid.startswith("msg_0") and len(mid) > 10:
        return mid, True
    uid = e.get("uuid")
    if isinstance(uid, str) and uid:
        return f"{nome}:{uid}", True
    return f"{nome}:#{linha}", False


def _uso(usage: dict[str, Any]) -> dict[str, int]:
    uso = {}
    for nosso, deles in CAMPOS_DE_USO:
        v = usage.get(deles)
        uso[nosso] = int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0
    uso["contexto"] = uso["entrada"] + uso["gravados"] + uso["relidos"]
    return uso


def _tool_uses(conteudo: Any) -> list[ToolUse]:
    if not isinstance(conteudo, list):
        return []
    saida = []
    for b in conteudo:
        if isinstance(b, dict) and b.get("type") == "tool_use" and isinstance(b.get("id"), str):
            entrada = b.get("input")
            nome = b.get("name")
            saida.append(ToolUse(b["id"], nome if isinstance(nome, str) else "",
                                 entrada if isinstance(entrada, dict) else {}))
    return saida


def _junta_tool_uses(destino: list[ToolUse], novos: list[ToolUse]) -> None:
    vistos = {t.id for t in destino}
    for t in novos:
        if t.id not in vistos:
            destino.append(t)
            vistos.add(t.id)


def _abertura(e: dict[str, Any], c: _Candidato, ts: datetime | None, linha: int
              ) -> Abertura | None:
    if e.get("toolUseResult") is not None or e.get("isCompactSummary") is True:
        return None
    msg = e.get("message")
    if not isinstance(msg, dict):
        return None
    conteudo = msg.get("content")
    if isinstance(conteudo, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in conteudo):
            return None
        texto = _texto_de(conteudo)
    elif isinstance(conteudo, str):
        texto = conteudo
    else:
        return None
    if not texto.strip() or texto.lstrip().startswith(INTERRUPCAO):
        return None
    m = _COMANDO.search(texto)
    if m:
        origem, comando = "comando", m.group(1)
    else:
        meta = e.get("isMeta") is True or texto.lstrip().startswith(AVISOS_DO_SISTEMA)
        origem, comando = ("meta" if meta else "humano"), None
    return Abertura(origem, c.nome, c.sessao, c.agente, ts, linha, texto, comando)


def _le_arquivo(c: _Candidato, g: _Global, de: datetime, ate: datetime,
                corte: datetime | None) -> Arquivo | None:
    """Stage one file against the global state; commit only when it has an entry in the
    window. ``corte`` drops this file's entries at or after it (the own session)."""
    uuids: set[str] = set()
    novas: dict[str, Chamada] = {}
    fundir: list[tuple[str, dict[str, int], list[ToolUse]]] = []
    resultados: dict[str, tuple[str, bool, Any]] = {}
    eventos: list[Chamada | Abertura] = []
    tipos: Counter[str] = Counter()
    linhas = ilegiveis = em_escrita = duplicadas = sem_chave = 0
    na_janela = tem_assistente = tem_uso = False
    primeiro: datetime | None = None
    ultimo: datetime | None = None

    with c.caminho.open("r", encoding="utf-8", errors="replace") as f:
        for numero, bruta in enumerate(f, start=1):
            if not bruta.strip():
                continue
            linhas += 1
            try:
                e = json.loads(bruta)
            except ValueError:
                # only a file's last line can lack its newline: one still being written
                if bruta.endswith("\n"):
                    ilegiveis += 1
                else:
                    em_escrita += 1
                continue
            if not isinstance(e, dict):
                ilegiveis += 1
                continue
            ts = _ts(e.get("timestamp"))
            if corte is not None and ts is not None and ts >= corte:
                continue
            uid = e.get("uuid")
            if isinstance(uid, str) and uid:
                if uid in g.uuids or uid in uuids:
                    duplicadas += 1
                    continue
                uuids.add(uid)
            tipo = e.get("type")
            if not isinstance(tipo, str) or tipo not in TIPOS_CONHECIDOS:
                tipos[tipo if isinstance(tipo, str) else "(sem tipo)"] += 1
            if ts is not None:
                if de <= ts <= ate:
                    na_janela = True
                if primeiro is None:
                    primeiro = ts
                ultimo = ts
            msg = e.get("message")
            if tipo == "assistant":
                tem_assistente = True
                if not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
                    continue
                tem_uso = True
                chave, real = _chave(e, msg, c.nome, numero)
                if not real:
                    sem_chave += 1
                uso = _uso(msg["usage"])
                tus = _tool_uses(msg.get("content"))
                if chave in novas:
                    ch = novas[chave]
                    # analyze-sessions.mjs 309-313 (Anthropic's session-report plugin,
                    # Apache-2.0, upstream path at _ROTULO): keep the usage with max
                    # output_tokens.
                    if uso["escritos"] >= ch.uso["escritos"]:
                        ch.uso = uso
                    _junta_tool_uses(ch.tool_uses, tus)
                elif chave in g.chamadas:
                    fundir.append((chave, uso, tus))
                else:
                    modelo = msg.get("model")
                    ch = Chamada(chave, c.nome, c.sessao, c.agente, ts, numero,
                                 modelo if isinstance(modelo, str) else None, uso, [])
                    _junta_tool_uses(ch.tool_uses, tus)
                    novas[chave] = ch
                    eventos.append(ch)
            elif tipo == "user":
                if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                    for b in msg["content"]:
                        if (isinstance(b, dict) and b.get("type") == "tool_result"
                                and isinstance(b.get("tool_use_id"), str)
                                and b["tool_use_id"] not in resultados):
                            resultados[b["tool_use_id"]] = (
                                _texto_de(b.get("content")), b.get("is_error") is True,
                                e.get("toolUseResult"))
                ab = _abertura(e, c, ts, numero)
                if ab is not None:
                    eventos.append(ab)

    if not na_janela:
        return None
    # commit
    g.uuids |= uuids
    g.linhas += linhas
    g.duplicadas += duplicadas
    g.sem_chave += sem_chave
    g.tipos.update(tipos)
    if ilegiveis:
        g.ilegiveis[c.nome] = ilegiveis
        g.formato_mudou = True
        g.avisos.append(f"{ilegiveis} linha(s) ilegível(is) em {c.nome}.")
    if em_escrita:
        g.em_escrita[c.nome] = em_escrita
    if tem_assistente and not tem_uso:
        g.formato_mudou = True
        g.avisos.append(f"{c.nome} tem respostas do modelo sem consumo (message.usage).")
    g.chamadas.update(novas)
    for chave, uso, tus in fundir:
        ch = g.chamadas[chave]
        if uso["escritos"] >= ch.uso["escritos"]:
            ch.uso = uso
        _junta_tool_uses(ch.tool_uses, tus)
    for tid, bruto in resultados.items():
        g.resultados_brutos.setdefault(tid, bruto)
    return Arquivo(c.nome, c.sessao, c.agente, c.principal, primeiro, ultimo, eventos)


def _primeiro_ts(caminho: Path) -> datetime | None:
    with caminho.open("r", encoding="utf-8", errors="replace") as f:
        for bruta in f:
            try:
                e = json.loads(bruta)
            except ValueError:
                continue  # counted when the file is read for real
            if isinstance(e, dict):
                ts = _ts(e.get("timestamp"))
                if ts is not None:
                    return ts
    return None


def _ordem(c: _Candidato) -> tuple[int, datetime, str]:
    sem = datetime.max.replace(tzinfo=timezone.utc)
    return (0 if c.primeiro is not None else 1, c.primeiro or sem, c.nome)


def _ordena_ajudantes(cands: list[_Candidato]) -> list[_Candidato]:
    """By first timestamp then name, a nested child right after its parent
    (analyze-sessions.mjs 548-556 sorts by birthtime for the same reason; Anthropic's
    session-report plugin, Apache-2.0, upstream path at ``_ROTULO``)."""
    cands = sorted(cands, key=_ordem)
    por_id = {c.agente: c for c in cands}
    filhos: dict[str, list[_Candidato]] = {}
    raizes: list[_Candidato] = []
    for c in cands:
        pai = (c.meta or {}).get("parentAgentId")
        if isinstance(pai, str) and pai in por_id and pai != c.agente:
            filhos.setdefault(pai, []).append(c)
        else:
            raizes.append(c)
    saida: list[_Candidato] = []
    vistos: set[str | None] = set()

    def emite(c: _Candidato) -> None:
        if c.agente in vistos:
            return
        vistos.add(c.agente)
        saida.append(c)
        for filho in filhos.get(c.agente or "", []):
            emite(filho)

    for c in raizes:
        emite(c)
    for c in cands:  # a cycle of parents: keep them, in plain order
        emite(c)
    return saida


def _tipo_do_ajudante(meta: dict[str, Any], tool_use_id: str | None,
                      do_pai: dict[str, str], arquivo: Path) -> tuple[str, str]:
    for fonte in ("customAgentType", "spawnedAgentType"):
        v = meta.get(fonte)
        if isinstance(v, str) and v:
            return v, fonte
    if tool_use_id is not None and tool_use_id in do_pai:
        return do_pai[tool_use_id], "subagent_type_do_pai"
    v = meta.get("agentType")
    if isinstance(v, str) and v:
        return v, "agentType"
    m = _ROTULO.match(arquivo.stem)
    if m:
        return m.group(1), "nome_do_arquivo"
    return "desconhecido", "desconhecido"


# ---------------------------------------------------------------- the whole read


def ler(pasta: Path, de: datetime, ate: datetime, propria: tuple[str, datetime] | None,
        excluidas: list[str], regra_da_pasta: str = "pasta") -> Leitura:
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise PastaAusente(f"a pasta de conversas não existe: {pasta}")
    fora = set(excluidas)
    g = _Global()
    metas_ilegiveis = 0

    def recente(p: Path) -> bool:
        return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) >= de

    principais: list[_Candidato] = []
    for p in sorted(pasta.glob("*.jsonl")):
        if p.stem in fora or not recente(p):
            continue
        principais.append(_Candidato(p, p.name, p.stem, None, True, _primeiro_ts(p)))

    ajudantes_c: list[_Candidato] = []
    for d in sorted(x for x in pasta.iterdir() if x.is_dir()):
        sub = d / "subagents"
        if d.name in fora or not sub.is_dir():
            continue
        for p in sorted(sub.rglob("agent-*.jsonl")):
            if not recente(p):
                continue
            primeiro = _primeiro_ts(p)
            if propria is not None and d.name == propria[0] and primeiro is not None \
                    and primeiro >= propria[1]:
                continue
            meta: dict[str, Any] | None = None
            mp = p.with_name(p.stem + ".meta.json")
            if mp.is_file():
                try:
                    lido = json.loads(mp.read_text(encoding="utf-8", errors="replace"))
                except ValueError:
                    lido = None
                    metas_ilegiveis += 1
                meta = lido if isinstance(lido, dict) else None
            ajudantes_c.append(_Candidato(p, p.relative_to(pasta).as_posix(), d.name,
                                          p.stem.removeprefix("agent-"), False, primeiro,
                                          meta))

    arquivos: list[Arquivo] = []
    for c in sorted(principais, key=_ordem):
        corte = propria[1] if propria is not None and c.sessao == propria[0] else None
        a = _le_arquivo(c, g, de, ate, corte)
        if a is not None:
            arquivos.append(a)
    lidos_aj: list[tuple[_Candidato, Arquivo]] = []
    for c in _ordena_ajudantes(ajudantes_c):
        a = _le_arquivo(c, g, de, ate, None)
        if a is not None:
            arquivos.append(a)
            lidos_aj.append((c, a))

    for a in arquivos:
        a.eventos.sort(key=lambda ev: ev.posicao)
    chamadas = [ev for a in arquivos for ev in a.eventos if isinstance(ev, Chamada)]
    aberturas = [ev for a in arquivos for ev in a.eventos if isinstance(ev, Abertura)]

    do_pai: dict[str, str] = {}
    comandos: dict[str, str] = {}
    for ch in chamadas:
        for t in ch.tool_uses:
            if t.nome in ("Agent", "Task") and isinstance(t.input.get("subagent_type"), str):
                do_pai[t.id] = t.input["subagent_type"]
            if isinstance(t.input.get("command"), str):
                comandos[t.id] = t.input["command"]
    resultados = {tid: desfecho(texto, erro, tur, comandos.get(tid))
                  for tid, (texto, erro, tur) in g.resultados_brutos.items()}

    fontes = dict.fromkeys(FONTES_DE_TIPO, 0)
    ajudantes: list[Ajudante] = []
    for c, a in lidos_aj:
        meta = c.meta or {}
        tuid = meta.get("toolUseId") if isinstance(meta.get("toolUseId"), str) else None
        tipo, fonte = _tipo_do_ajudante(meta, tuid, do_pai, c.caminho)
        fontes[fonte] += 1
        equipe = "teamName" in meta
        if equipe and fonte not in ("customAgentType", "spawnedAgentType",
                                    "subagent_type_do_pai"):
            g.formato_mudou = True
            g.avisos.append(f"um ajudante de equipe em {c.nome} não diz o próprio tipo "
                            "(sem customAgentType, spawnedAgentType nem subagent_type do pai).")
        pai = meta.get("parentAgentId")
        modelo = meta.get("model")
        ajudantes.append(Ajudante(
            c.agente or "", c.sessao, c.nome, tipo, fonte, tuid,
            pai if isinstance(pai, str) else None,
            modelo if isinstance(modelo, str) else None, equipe,
            a.primeiro_timestamp, a.ultimo_timestamp))

    if g.sem_chave:
        g.avisos.append(f"{g.sem_chave} resposta(s) do modelo sem requestId, id nem uuid: "
                        "cada linha contada uma vez.")
    if metas_ilegiveis:
        g.avisos.append(f"{metas_ilegiveis} arquivo(s) .meta.json ilegível(is): "
                        "tipo lido de outra fonte.")

    excl = sorted(fora)
    if propria is not None:
        excl.append(f"{propria[0]} desde {hora_local(propria[1])}")
    regua: dict[str, Any] = {
        "fonte": str(pasta.resolve()),
        "regra_da_pasta": regra_da_pasta,
        "fuso": _NOME_DO_FUSO or "local",
        "janela": {"de": hora_local(de), "ate": hora_local(ate)},
        "medido_em": datetime.now(timezone.utc).astimezone(_FUSO).isoformat(timespec="seconds"),
        "arquivos_lidos": {"principais": sum(1 for a in arquivos if a.principal),
                           "ajudantes": len(lidos_aj)},
        "linhas_lidas": g.linhas,
        "linhas_ilegiveis": dict(g.ilegiveis),
        "linhas_em_escrita": dict(g.em_escrita),
        "tipos_desconhecidos": dict(g.tipos),
        "excluidas": excl,
        "duplicadas_por_uuid": g.duplicadas,
        "tipo_de_ajudante_por_fonte": fontes,
        "padroes": {"abre": None, "fecha": None, "resposta": None, "acao": []},
        "padroes_casados": {"abre": None, "fecha": None, "resposta": None, "acao": []},
        "formato_mudou": g.formato_mudou,
        "avisos": list(g.avisos),
    }
    sessoes = [Sessao(a.sessao, a.nome, a.primeiro_timestamp, a.ultimo_timestamp)
               for a in arquivos if a.principal]
    return Leitura(arquivos, sessoes, ajudantes, chamadas, aberturas, resultados, regua)
