"""fabrica.py — writes fixture transcripts in the shape Claude Code records them.

``Transcrito`` appends one JSON line per call to its file; every method returns ``self`` so a
test reads as a little story. Times are local text in ``FUSO_TESTE`` ("2026-11-10T10:00" or
with seconds) and are written as UTC "...Z" like the real files.

The sentinel ``SENTINELA`` is planted in message text, tool inputs (commands, file paths),
tool results and a meta's ``name``/``description`` — never in fields the reader may print.

Line uuids are random unless ``ids_fixos()`` is active: inside it they come from a counter,
so the same story writes the same bytes every time.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import uuid as _uuid
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SENTINELA = "SENTINELA-PRIVADA"
FUSO_TESTE = "America/New_York"  # has DST, so every time assertion stays meaningful
FUSO = ZoneInfo(FUSO_TESTE)


def _uuid_aleatorio() -> str:
    return str(_uuid.uuid4())


_novo_id: Callable[[], str] = _uuid_aleatorio


@contextlib.contextmanager
def ids_fixos() -> Iterator[None]:
    """Counter-based uuids (``00000000-0000-4000-8000-000000000001``, …) while active."""
    global _novo_id
    antes = _novo_id
    contador = itertools.count(1)
    _novo_id = lambda: f"00000000-0000-4000-8000-{next(contador):012d}"  # noqa: E731
    try:
        yield
    finally:
        _novo_id = antes


def z(t: str) -> str:
    """Local text to the real files' UTC form."""
    formato = "%Y-%m-%dT%H:%M:%S" if t.count(":") == 2 else "%Y-%m-%dT%H:%M"
    local = datetime.strptime(t, formato).replace(tzinfo=FUSO)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def uso(entrada: int = 1, gravados: int = 0, relidos: int = 0, escritos: int = 1
        ) -> dict[str, int]:
    return {"input_tokens": entrada, "cache_creation_input_tokens": gravados,
            "cache_read_input_tokens": relidos, "output_tokens": escritos}


def tu(id: str, nome: str = "Bash", **entrada: Any) -> dict[str, Any]:
    if not entrada:
        entrada = {"command": f"echo {SENTINELA}", "file_path": f"/x/{SENTINELA}.md"}
    return {"type": "tool_use", "id": id, "name": nome, "input": entrada}


class Transcrito:
    def __init__(self, caminho: Path, sessao: str, agente: str | None = None) -> None:
        self.caminho = caminho
        self.sessao = sessao
        self.agente = agente
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.touch()
        self._anterior: str | None = None

    def _linha(self, obj: dict[str, Any]) -> Transcrito:
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj) + "\n")
        return self

    def _base(self, t: str, tipo: str, uuid: str | None = None, **extra: Any
              ) -> dict[str, Any]:
        u = uuid or _novo_id()
        obj: dict[str, Any] = {"type": tipo, "uuid": u, "parentUuid": self._anterior,
                               "timestamp": z(t), "sessionId": self.sessao,
                               "isSidechain": self.agente is not None}
        if self.agente is not None:
            obj["agentId"] = self.agente
        obj.update(extra)
        self._anterior = u
        return obj

    def bruto(self, obj: dict[str, Any]) -> Transcrito:
        return self._linha(obj)

    def humano(self, t: str, txt: str = f"oi {SENTINELA}", uuid: str | None = None,
               blocos: bool = False) -> Transcrito:
        conteudo: Any = [{"type": "text", "text": txt}] if blocos else txt
        return self._linha(self._base(t, "user", uuid,
                                      message={"role": "user", "content": conteudo}))

    def meta(self, t: str, txt: str = f"[routine] {SENTINELA}", uuid: str | None = None
             ) -> Transcrito:
        return self._linha(self._base(t, "user", uuid, isMeta=True,
                                      message={"role": "user", "content": txt}))

    def comando(self, t: str, nome: str, uuid: str | None = None) -> Transcrito:
        nome = nome.lstrip("/")
        txt = (f"<command-message>{nome}</command-message>\n"
               f"<command-name>/{nome}</command-name>\n"
               f"<command-args>{SENTINELA}</command-args>")
        return self._linha(self._base(t, "user", uuid,
                                      message={"role": "user", "content": txt}))

    def primeiro_pedido(self, t: str, txt: str = f"faça {SENTINELA}") -> Transcrito:
        return self.humano(t, txt)

    def interrompe(self, t: str) -> Transcrito:
        return self.humano(t, "[Request interrupted by user]")

    def assistente(self, t: str, req: str | None, usage: dict[str, int] | None = None,
                   tool_uses: list[dict[str, Any]] | None = None, msg_id: str | None = None,
                   uuid: str | None = None, modelo: str = "claude-opus-5-5",
                   sem_uso: bool = False) -> Transcrito:
        conteudo: list[dict[str, Any]] = [{"type": "text", "text": f"vou {SENTINELA}"}]
        conteudo += tool_uses or []
        msg: dict[str, Any] = {"role": "assistant", "model": modelo, "content": conteudo}
        if msg_id is not None:
            msg["id"] = msg_id
        if not sem_uso:
            msg["usage"] = usage or uso()
        extra: dict[str, Any] = {"message": msg}
        if req is not None:
            extra["requestId"] = req
        return self._linha(self._base(t, "assistant", uuid, **extra))

    def resultado(self, t: str, tool_id: str, texto: str = f"feito {SENTINELA}",
                  is_error: bool = False, tool_use_result: Any = None,
                  blocos: bool = False) -> Transcrito:
        conteudo: Any = [{"type": "text", "text": texto}] if blocos else texto
        bloco = {"type": "tool_result", "tool_use_id": tool_id, "content": conteudo,
                 "is_error": is_error}
        tur = tool_use_result if tool_use_result is not None else {
            "stdout": texto, "stderr": "", "interrupted": False}
        return self._linha(self._base(t, "user", None, toolUseResult=tur,
                                      message={"role": "user", "content": [bloco]}))

    def compacta(self, t: str) -> Transcrito:
        return self._linha(self._base(t, "user", None, isCompactSummary=True,
                                      message={"role": "user",
                                               "content": f"resumo {SENTINELA}"}))

    def linha_quebrada(self) -> Transcrito:
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write('{"type": "user", "message": {"content": "' + SENTINELA + '\n')
        return self

    def linha_cortada(self) -> Transcrito:
        """A last line still being written: half a JSON object and no newline."""
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write('{"type": "assistant", "message": {"content": "' + SENTINELA)
        return self

    def api_request_blob(self, t: str) -> Transcrito:
        return self._linha(self._base(
            t, "api-request-blob", None,
            message={"role": "user", "content": f"pedido {SENTINELA}"}))

    def tipo(self, t: str, nome: str) -> Transcrito:
        return self._linha(self._base(t, nome, None))


def sessao(pasta: Path, id: str) -> Transcrito:
    return Transcrito(pasta / f"{id}.jsonl", id)


def ajudante(pasta: Path, sessao_id: str, agente_id: str,
             meta: dict[str, Any] | None = None, com_meta: bool = True,
             subpasta: str = "") -> Transcrito:
    """A sub-agent file ``<pasta>/<sessao>/subagents/[subpasta/]agent-<id>.jsonl`` and its
    meta. The meta always carries a private ``name``/``description`` unless given."""
    base = pasta / sessao_id / "subagents"
    if subpasta:
        base = base / subpasta
    t = Transcrito(base / f"agent-{agente_id}.jsonl", sessao_id, agente_id)
    if com_meta:
        m = {"name": f"nome {SENTINELA}", "description": f"tarefa {SENTINELA}"}
        m.update(meta or {})
        (base / f"agent-{agente_id}.meta.json").write_text(json.dumps(m), encoding="utf-8")
    return t
