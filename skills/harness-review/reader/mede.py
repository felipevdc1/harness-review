"""mede.py — the command line of harness-review: one verb, one JSON answer, nothing written.

Verb:

- ``execucoes``  the runs of one routine or skill in a window and what each cost
                 (``execucoes.execucoes`` over ``transcritos.ler``).

Flags (see README.md, which documents every one): ``--pasta``, ``--de``, ``--ate``,
``--sessao-propria`` + ``--desde`` or ``--sem-sessao-propria`` (exactly one form),
``--exclui-sessao`` (repeatable), ``--abre``, ``--fecha``, ``--resposta``, ``--acao``
(repeatable), ``--prazo-uso-h``, ``--fuso``.

Guarantees:

1. Exit 0: one JSON object on stdout (UTF-8, ``ensure_ascii=False``, sorted keys), even when
   the ruler carries ``avisos`` or ``formato_mudou``.
2. Exit 2: bad arguments (a missing own-session form, a bad date, a bad pattern, an unknown
   ``--fuso``) or a missing folder, with one plain Portuguese sentence on stderr and nothing on stdout; never a
   traceback, never a partial answer.
3. Reads only; imports only the standard library and the two sibling modules.
4. ``--fuso`` is applied (``transcritos.define_fuso``) before any date is parsed; without it,
   local times follow the machine's own rules. Without ``--pasta`` the folder comes from
   ``transcritos.pasta_padrao`` with the own-session id, and the ruler's ``regra_da_pasta``
   says which rule picked it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import execucoes as ex  # noqa: E402
import transcritos as tr  # noqa: E402

FRASE_SESSAO = ("diga qual é a sessão desta medição e quando ela começou "
                "(--sessao-propria … --desde …) ou --sem-sessao-propria")


class _Erro(Exception):
    """A plain sentence for stderr, exit 2."""


def _data(texto: str, onde: str, fim_do_dia: bool = False) -> datetime:
    try:
        return tr.para_utc(texto, fim_do_dia=fim_do_dia)
    except ValueError:
        raise _Erro(f"{onde} precisa de uma data AAAA-MM-DD ou AAAA-MM-DDTHH:MM "
                    f"(veio {texto!r}).") from None


def _desde(texto: str) -> datetime:
    """AAAA-MM-DDTHH:MM in local time (or --fuso), or a full ISO timestamp with its offset."""
    try:
        return tr.para_utc(texto)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError:
        dt = None
    if dt is None or dt.tzinfo is None:
        raise _Erro(f"--desde precisa de AAAA-MM-DDTHH:MM (hora local, ou --fuso) ou de uma "
                    f"hora ISO com fuso, como 2026-11-15T13:47:00-05:00 (veio {texto!r}).")
    return dt.astimezone(timezone.utc)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mede.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="verbo", required=True)
    e = sub.add_parser("execucoes", help="as execuções de uma rotina ou skill numa janela")
    e.add_argument("--pasta", help="pasta das conversas (padrão: a do projeto atual)")
    e.add_argument("--de", required=True, help="início da janela, AAAA-MM-DD[THH:MM]")
    e.add_argument("--ate", required=True, help="fim da janela, AAAA-MM-DD[THH:MM]")
    e.add_argument("--sessao-propria", help="id da sessão que está medindo")
    e.add_argument("--desde", help="quando a sessão que está medindo começou")
    e.add_argument("--sem-sessao-propria", action="store_true",
                   help="nenhuma sessão desta medição a deixar de fora")
    e.add_argument("--exclui-sessao", action="append", default=[],
                   help="sessão inteira a deixar de fora (repetível)")
    e.add_argument("--abre", required=True,
                   help="skill:<nome>, texto:<regex> ou comando:<regex>")
    e.add_argument("--fecha", help="texto:<regex> ou comando:<regex>")
    e.add_argument("--resposta", help="regex de uma mensagem que conta como resposta")
    e.add_argument("--acao", action="append", default=[],
                   help="comando:<regex> que conta como ação (repetível)")
    e.add_argument("--prazo-uso-h", type=float, default=24,
                   help="horas para procurar resposta ou ação (padrão 24)")
    e.add_argument("--fuso", help="fuso IANA das horas lidas e mostradas, como "
                   "America/New_York (padrão: o do computador)")
    return p


def _responde(a: argparse.Namespace) -> dict:
    try:
        tr.define_fuso(a.fuso)
    except ValueError as erro:
        raise _Erro(str(erro)) from None
    if a.sem_sessao_propria:
        if a.sessao_propria is not None or a.desde is not None:
            raise _Erro(FRASE_SESSAO)
        propria = None
    else:
        if a.sessao_propria is None or a.desde is None:
            raise _Erro(FRASE_SESSAO)
        propria = (a.sessao_propria.removeprefix("claude:"), _desde(a.desde))
    de = _data(a.de, "--de")
    ate = _data(a.ate, "--ate", fim_do_dia=True)
    if ate < de:
        raise _Erro("--ate vem antes de --de: a janela está ao contrário.")
    if a.pasta:
        pasta, regra = Path(a.pasta), "pasta"
    else:
        pasta, regra = tr.pasta_padrao(propria[0] if propria is not None else None)
    try:
        leitura = tr.ler(pasta, de, ate, propria, a.exclui_sessao, regra)
    except tr.PastaAusente as erro:
        raise _Erro(f"{erro}.") from None
    try:
        return ex.execucoes(leitura, a.abre, a.fecha, a.resposta, a.acao, a.prazo_uso_h)
    except ValueError as erro:
        raise _Erro(str(erro)) from None


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        resposta = _responde(a)
    except _Erro as erro:
        print(erro, file=sys.stderr)
        return 2
    texto = json.dumps(resposta, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.buffer.write((texto + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
