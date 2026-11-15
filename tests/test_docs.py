"""Pins the reader's README.md against mede.py and its answer, so the two can never drift apart.

- every verb of ``mede.py`` (``add_parser("<verb>")``) appears in the README as a full command
  line, ``mede.py <verb>``;
- every flag of ``mede.py`` (the ``--`` option strings of ``add_argument``) appears in the README
  as a whole flag, not as part of a longer one;
- every flag, and every key of a real answer (the top level, one run of ``execucoes``, a cost
  block, ``comandos``, ``totais`` and ``regua``), has a row ``| `name` | meaning |`` in the
  README's ``## Glossary`` table; every such key is also named in the ``## The answer``
  section.

Verbs and flags are read from the source by AST and keys from a real answer, never from a list
kept here, so a new flag or key with no README line turns red. Each ruler is validated both
ways before it is trusted (a known-bad text is flagged, the real README is quiet). README.md is
never written to; the bad cases work on copies in memory.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from fabrica import sessao, tu

import transcritos as tr
from execucoes import execucoes

LEITOR = Path(__file__).resolve().parents[1] / "skills" / "harness-review" / "reader"
README = LEITOR / "README.md"
MEDE = LEITOR / "mede.py"


def da_fonte(fonte: str) -> tuple[list[str], list[str]]:
    """(verbs, flags) an argparse CLI declares."""
    verbos: list[str] = []
    flags: list[str] = []
    for no in ast.walk(ast.parse(fonte)):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
            continue
        textos = [a.value for a in no.args
                  if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if no.func.attr == "add_parser" and textos:
            verbos.append(textos[0])
        elif no.func.attr == "add_argument":
            flags += [t for t in textos if t.startswith("--")]
    return verbos, flags


def verbos_faltando(verbos: list[str], doc: str) -> list[str]:
    return [v for v in verbos if f"mede.py {v}" not in doc]


def flags_faltando(flags: list[str], doc: str) -> list[str]:
    return [f for f in flags if not re.search(rf"(?<![\w-]){re.escape(f)}(?![\w-])", doc)]


def secao(doc: str, titulo: str) -> str:
    """The text under ``## <titulo>`` up to the next ``## `` heading ('' when absent)."""
    m = re.search(rf"^## {re.escape(titulo)}[ \t]*\n(.*?)(?=^## |\Z)", doc, re.M | re.S)
    return m.group(1) if m else ""


def glossario(doc: str) -> set[str]:
    """Names with a row ``| `name` | non-empty meaning |`` under ``## Glossary``."""
    return set(re.findall(r"^\|\s*`([^`]+)`\s*\|\s*[^|\s][^|]*\|\s*$",
                          secao(doc, "Glossary"), re.M))


def chaves_da_resposta(pasta: Path) -> set[str]:
    """The keys of a real answer: top level, a run, a cost block, comandos, totais, regua."""
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", "[routine] x")
    s.assistente("2026-11-10T10:01", "r1", tool_uses=[tu("b1", command="ls")])
    s.resultado("2026-11-10T10:02", "b1")
    leitura = tr.ler(pasta, tr.para_utc("2026-11-10"),
                     tr.para_utc("2026-11-12", fim_do_dia=True), None, [])
    r = execucoes(leitura, r"texto:^\[routine\]", None, None, [])
    run = r["execucoes"][0]
    return (set(r) | set(run) | set(run["largo"]) | set(run["comandos"]) | set(r["totais"])
            | set(r["regua"]))


def _doc() -> str:
    return README.read_text(encoding="utf-8")


# ---------------------------------------------------------------- the rulers, both ways


def test_regua_le_verbos_e_flags():
    codigo = ("sub.add_parser('roda', help='x')\n"
              "p.add_argument('--um', '-u')\np.add_argument('--dois', action='append')\n"
              "p.add_argument('posicional')\n")
    assert da_fonte(codigo) == (["roda"], ["--um", "--dois"])


def test_o_cli_real_tem_o_que_deve():
    """Guard against a ruler that finds nothing and passes vacuously."""
    verbos, flags = da_fonte(MEDE.read_text(encoding="utf-8"))
    assert verbos == ["execucoes"]
    assert len(flags) == 13 and "--sem-sessao-propria" in flags and "--prazo-uso-h" in flags
    assert "--fuso" in flags


def test_flag_dentro_de_outra_mais_longa_nao_conta():
    assert flags_faltando(["--sessao-propria"], "use --sem-sessao-propria") == ["--sessao-propria"]
    assert flags_faltando(["--sessao-propria"], "use `--sessao-propria` x") == []


def test_regua_acusa_doc_sem_uma_flag_e_sem_o_verbo():
    doc = _doc()
    sem = doc.replace("--prazo-uso-h", "--prazo")
    assert sem != doc, "the replace hit nothing: the test would prove nothing"
    _, flags = da_fonte(MEDE.read_text(encoding="utf-8"))
    assert flags_faltando(flags, sem) == ["--prazo-uso-h"]
    sem_verbo = doc.replace("mede.py execucoes", "mede.py")
    assert sem_verbo != doc
    assert verbos_faltando(["execucoes"], sem_verbo) == ["execucoes"]


def test_regua_do_glossario_ambos_os_lados():
    doc = ("# x\n\n## Glossary\n\n| Name | Meaning |\n|---|---|\n"
           "| `--fuso` | the zone |\n| `regua` | the ruler |\n| `vazio` |  |\n\n"
           "## Other\n\n| `fora` | not in the glossary |\n")
    assert glossario(doc) == {"--fuso", "regua"}  # an empty meaning is no row
    assert glossario("# x\n\n| `--fuso` | the zone |\n") == set()  # no section, no rows
    assert secao(doc, "Other").strip() == "| `fora` | not in the glossary |"


def test_as_chaves_da_resposta_nao_sao_vazias(pasta):
    """Guard against a key ruler that finds nothing and passes vacuously."""
    chaves = chaves_da_resposta(pasta)
    assert {"execucoes", "totais", "regua", "sessao", "entrada", "por_desfecho", "fuso",
            "regra_da_pasta", "fonte", "medido_em", "n", "uso_indefinido"} <= chaves


def test_regua_acusa_linha_do_glossario_faltando(pasta):
    doc = _doc()
    sem = doc.replace("| `regra_da_pasta` |", "| regra_da_pasta |")
    assert sem != doc, "the replace hit nothing: the test would prove nothing"
    assert chaves_da_resposta(pasta) - glossario(sem) == {"regra_da_pasta"}
    sem_flag = doc.replace("| `--fuso` |", "| --fuso |")
    assert sem_flag != doc
    _, flags = da_fonte(MEDE.read_text(encoding="utf-8"))
    assert set(flags) - glossario(sem_flag) == {"--fuso"}


# ---------------------------------------------------------------- the real README


def test_readme_tem_todo_verbo_e_toda_flag():
    verbos, flags = da_fonte(MEDE.read_text(encoding="utf-8"))
    assert verbos_faltando(verbos, _doc()) == []
    assert flags_faltando(flags, _doc()) == []


def test_glossario_tem_toda_flag_e_toda_chave(pasta):
    _, flags = da_fonte(MEDE.read_text(encoding="utf-8"))
    falta = (set(flags) | chaves_da_resposta(pasta)) - glossario(_doc())
    assert falta == set()


def test_secao_da_resposta_nomeia_toda_chave(pasta):
    resposta = secao(_doc(), "The answer")
    assert resposta, "the README has no '## The answer' section"
    falta = {k for k in chaves_da_resposta(pasta) if f"`{k}`" not in resposta}
    assert falta == set()
