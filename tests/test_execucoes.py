"""The verb execucoes, each rule with the case that must fail when the rule is broken."""
from __future__ import annotations

import json

import pytest
from fabrica import SENTINELA, ajudante, sessao, tu, uso

import transcritos as tr
from execucoes import execucoes

ROTINA = r"texto:^\[routine\] read queue/next\.md"
TXT_ROTINA = f"[routine] read queue/next.md {SENTINELA}"


def le(pasta, de="2026-11-10", ate="2026-11-12", propria=None, excluidas=()):
    return tr.ler(pasta, tr.para_utc(de), tr.para_utc(ate, fim_do_dia=True), propria,
                  list(excluidas))


def mede(pasta, abre=ROTINA, fecha=None, resposta=None, acoes=(), prazo_uso_h=24, **kw):
    return execucoes(le(pasta, **kw), abre, fecha, resposta, list(acoes), prazo_uso_h)


def numero(x):
    return x["contexto"] + x["escritos"]


# ---------------------------------------------------------------- patterns


@pytest.mark.parametrize("abre,fecha,resposta,acoes", [
    ("rotina", None, None, []),
    ("skill:", None, None, []),
    ("texto:(", None, None, []),
    (ROTINA, "skill:x", None, []),
    (ROTINA, None, "[", []),
    (ROTINA, None, None, ["texto:x"]),
])
def test_padrao_ruim_da_valueerror_em_portugues(pasta, abre, fecha, resposta, acoes):
    with pytest.raises(ValueError, match="padrão de"):
        execucoes(le(pasta), abre, fecha, resposta, acoes)


def test_padroes_ecoados_na_regua_e_pasta_vazia(pasta):
    r = mede(pasta, fecha="comando:x", resposta="ok", acoes=["comando:y"])
    assert r["execucoes"] == []
    assert r["totais"]["n"] == 0 and r["totais"]["largo"]["mediana"] is None
    assert r["regua"]["padroes"] == {"abre": ROTINA, "fecha": "comando:x",
                                     "resposta": "ok", "acao": ["comando:y"]}
    assert "formato_mudou" in r["regua"]


# ---------------------------------------------------------------- opening and closing


def test_rotina_meta_abre_e_aviso_de_ajudante_nao_fecha(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1", uso(escritos=10))
    s.meta("2026-11-10T10:02", f"<task-notification> {SENTINELA}")  # sub-agent notice
    s.assistente("2026-11-10T10:03", "r2", uso(escritos=20))
    s.humano("2026-11-10T11:00")
    s.assistente("2026-11-10T11:01", "r3", uso(escritos=99))
    r = mede(pasta)
    [e] = r["execucoes"]
    assert e["largo"]["chamadas"] == 2 and e["largo"]["escritos"] == 30
    assert e["fim"] == "2026-11-10T10:03:00-05:00"


def test_rotina_sem_is_meta_e_aviso_de_ajudante_sem_is_meta_nao_fecha(pasta):
    """Real shape (07/11-15/11): neither the [routine] line nor the notice carries isMeta."""
    s = sessao(pasta, "s1").humano("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1", uso(escritos=10))
    s.humano("2026-11-10T10:02", f"<task-notification> {SENTINELA}")
    s.assistente("2026-11-10T10:03", "r2", uso(escritos=20))
    s.assistente("2026-11-10T10:04", "r3", uso(escritos=40))
    s.humano("2026-11-10T11:00")
    s.assistente("2026-11-10T11:01", "r4", uso(escritos=99))
    [e] = mede(pasta)["execucoes"]
    assert e["largo"]["chamadas"] == 3 and e["largo"]["escritos"] == 70
    assert e["fim"] == "2026-11-10T10:04:00-05:00"


def test_corrida_termina_na_proxima_rotina(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1")
    s.meta("2026-11-10T12:00", TXT_ROTINA).assistente("2026-11-10T12:01", "r2")
    s.assistente("2026-11-10T12:02", "r3")
    r = mede(pasta)
    assert [e["largo"]["chamadas"] for e in r["execucoes"]] == [1, 2]


def test_fecha_estica_ate_o_ultimo_confere(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T21:00", TXT_ROTINA)
    s.assistente("2026-11-10T21:01", "r1", tool_uses=[tu("c1", command="faq.py confere 1")])
    s.resultado("2026-11-10T21:02", "c1", "Exit code 1", is_error=True)
    s.humano("2026-11-10T21:10")  # ends the run without --fecha
    s.assistente("2026-11-10T21:11", "r2", tool_uses=[tu("c2", command="faq.py confere 1")])
    s.resultado("2026-11-10T21:12", "c2", "ok")
    s.assistente("2026-11-10T21:13", "r3")
    s.assistente("2026-11-10T21:20", "r4")
    sem = mede(pasta)["execucoes"][0]
    com = mede(pasta, fecha=r"comando:faq\.py confere")["execucoes"][0]
    assert sem["largo"]["chamadas"] == 1
    assert com["largo"]["chamadas"] == 3  # r1, r2 and r2's next call r3; not r4
    assert com["estreito"]["chamadas"] == 3
    assert com["comandos"]["mais_de_uma_tentativa"] is True


@pytest.mark.parametrize("como", ["skill_call", "digitado"])
def test_skill_abre_por_chamada_ou_comando_digitado(pasta, como):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00")
    if como == "skill_call":
        s.assistente("2026-11-10T10:01", "r0")
        s.assistente("2026-11-10T10:02", "r1", tool_uses=[tu("k1", "Skill", skill="email")])
    else:
        s.comando("2026-11-10T10:02", "/email")
        s.assistente("2026-11-10T10:03", "r1", tool_uses=[tu("k1", "Skill", skill="email")])
    s.assistente("2026-11-10T10:04", "r2")
    r = mede(pasta, abre="skill:email")
    [e] = r["execucoes"]
    assert e["largo"]["chamadas"] == 2


def test_texto_no_primeiro_pedido_do_ajudante_vai_ate_o_fim_do_arquivo(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00").assistente("2026-11-10T10:01", "r0")
    a = ajudante(pasta, "s1", "akeeper", meta={"agentType": "general-purpose"})
    a.primeiro_pedido("2026-11-10T10:02", f"Run the nightly-notes procedure {SENTINELA}")
    a.assistente("2026-11-10T10:03", "r1").assistente("2026-11-10T10:04", "r2")
    a.meta("2026-11-10T10:05", f"hook feedback {SENTINELA}")
    a.assistente("2026-11-10T10:06", "r3")
    r = mede(pasta, abre="texto:Run the nightly-notes procedure")
    [e] = r["execucoes"]
    assert e["agente"] == "akeeper" and e["sessao"] == "s1"
    assert e["largo"]["chamadas"] == 3


def test_estreito_e_largo_diferem_quando_o_turno_mistura_trabalho(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    for i in range(4):
        s.assistente(f"2026-11-10T10:0{i + 1}", f"r{i}", uso(entrada=100, escritos=10))
    e = mede(pasta)["execucoes"][0]
    assert e["estreito"]["chamadas"] == 1 and e["largo"]["chamadas"] == 4
    assert numero(e["estreito"]) < numero(e["largo"])


# ---------------------------------------------------------------- sub-agents


def test_ajudante_por_tool_use_id_e_colega_de_equipe_pelo_tipo_real(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T21:00", TXT_ROTINA)
    s.assistente("2026-11-10T21:01", "r1", tool_uses=[
        tu("ag1", "Agent", subagent_type="faq-juiz", prompt=SENTINELA)])
    s.assistente("2026-11-10T21:30", "r2")
    j = ajudante(pasta, "s1", "ajuiz", meta={"toolUseId": "ag1"})
    j.primeiro_pedido("2026-11-10T21:02").assistente("2026-11-10T21:03", "j1", uso(escritos=5))
    eq = ajudante(pasta, "s1", "faq-extrator-1020",
                  meta={"teamName": "faq", "customAgentType": "faq-extrator",
                        "agentType": "faq-extrator-1020"})
    eq.primeiro_pedido("2026-11-10T21:05").assistente("2026-11-10T21:06", "x1")
    eq.assistente("2026-11-10T21:07", "x2")
    e = mede(pasta)["execucoes"][0]
    assert set(e["ajudantes"]) == {"faq-juiz", "faq-extrator"}
    assert e["ajudantes"]["faq-extrator"]["quantos"] == 1
    assert e["ajudantes"]["faq-extrator"]["chamadas"] == 2
    assert e["ajudantes"]["faq-extrator"]["acordar"]["chamadas"] == 1
    assert e["ajudantes"]["faq-juiz"]["modelos"] == ["claude-opus-5-5"]
    assert "atribuido_por_hora" in e["sinais"]
    assert e["largo"]["chamadas"] == 2 + 1 + 2


def test_colega_fora_da_corrida_nao_entra(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T21:00", TXT_ROTINA)
    s.assistente("2026-11-10T21:01", "r1")
    eq = ajudante(pasta, "s1", "faq-extrator-1020",
                  meta={"teamName": "faq", "customAgentType": "faq-extrator"})
    eq.primeiro_pedido("2026-11-10T23:00").assistente("2026-11-10T23:01", "x1")
    e = mede(pasta)["execucoes"][0]
    assert e["ajudantes"] == {} and e["sinais"] == []


def test_acordar_so_a_primeira_chamada_principal_e_ajudante_separados(pasta):
    s = sessao(pasta, "s1").humano("2026-11-09T08:00")
    s.assistente("2026-11-09T08:01", "r0", uso(relidos=90000, escritos=1))
    s.meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1", uso(relidos=150000), tool_uses=[
        tu("ag1", "Agent", subagent_type="helper-analyst")])
    a = ajudante(pasta, "s1", "aouv", meta={"toolUseId": "ag1"})
    a.primeiro_pedido("2026-11-10T10:02")
    a.assistente("2026-11-10T10:03", "a1", uso(gravados=7000))
    a.assistente("2026-11-10T10:04", "a2", uso(relidos=8000))
    e = mede(pasta)["execucoes"][0]
    assert e["acordar"]["chamadas"] == 1 and e["acordar"]["relidos"] == 90000
    assert "sessao_comecou_antes" in e["sinais"]
    aj = e["ajudantes"]["helper-analyst"]["acordar"]
    assert aj["chamadas"] == 1 and aj["gravados"] == 7000 and aj["relidos"] == 0


def test_sessao_que_comeca_na_janela_nao_tem_sinal(pasta):
    sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA) \
        .assistente("2026-11-10T10:01", "r1")
    assert mede(pasta)["execucoes"][0]["sinais"] == []


# ---------------------------------------------------------------- commands


def test_comandos_negacao_de_gancho_e_saida_real(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T21:00", TXT_ROTINA)
    s.assistente("2026-11-10T21:01", "r1", tool_uses=[tu("b1", command="cd x && faq.py a")])
    s.resultado("2026-11-10T21:01", "b1", "PreToolUse:Bash hook error: no", is_error=True)
    s.assistente("2026-11-10T21:02", "r2", tool_uses=[tu("b2", command="cd y && faq.py b")])
    s.resultado("2026-11-10T21:02", "b2", "PreToolUse:Bash hook error: no", is_error=True)
    s.assistente("2026-11-10T21:03", "r3", tool_uses=[tu("b3", command="faq.py confere")])
    s.resultado("2026-11-10T21:03", "b3", "Exit code 1\nfalhou", is_error=True)
    e = mede(pasta)["execucoes"][0]
    assert e["comandos"]["por_desfecho"] == {"negado_por_gancho": 2, "saida_1": 1}
    assert e["comandos"]["mais_de_uma_tentativa"] is False


def test_nova_tentativa_que_termina_ok(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T21:00", TXT_ROTINA)
    s.assistente("2026-11-10T21:01", "r1", tool_uses=[tu("b1", command="faq.py confere")])
    s.resultado("2026-11-10T21:01", "b1", "Exit code 1", is_error=True)
    s.assistente("2026-11-10T21:02", "r2", tool_uses=[tu("b2", command="faq.py confere")])
    s.resultado("2026-11-10T21:02", "b2", "tudo certo")
    e = mede(pasta)["execucoes"][0]
    assert e["comandos"]["por_desfecho"] == {"saida_1": 1, "ok": 1}
    assert e["comandos"]["mais_de_uma_tentativa"] is True


# ---------------------------------------------------------------- window


def test_corrida_que_cruza_o_fim_da_janela(pasta):
    s = sessao(pasta, "s1").meta("2026-11-12T23:50", TXT_ROTINA)
    s.assistente("2026-11-12T23:55", "r1").assistente("2026-11-13T00:10", "r2")
    s.meta("2026-11-13T09:00", TXT_ROTINA).assistente("2026-11-13T09:01", "r3")
    r = mede(pasta)
    [e] = r["execucoes"]  # the 13/11 run opens outside the window
    assert "corta_janela" in e["sinais"] and e["largo"]["chamadas"] == 2


# ---------------------------------------------------------------- was the result used


def _canal(t, texto):
    return f'<channel source="chat" ts="{t}">{texto} {SENTINELA}</channel>'


def test_respondido_por_mensagem_do_canal(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA)
    s.assistente("2026-11-10T20:01", "r1")
    s.meta("2026-11-10T20:30", _canal("x", "completa 3"))
    s.assistente("2026-11-10T20:31", "r2")
    e = mede(pasta, resposta=r'source="chat"')["execucoes"][0]
    assert e["respondido"] is True and e["minutos_ate_resposta"] == 30.0
    assert e["agido"] is None and e["uso_indefinido"] is False


def test_mensagem_humana_sem_relacao_nao_e_resposta(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA)
    s.assistente("2026-11-10T20:01", "r1")
    s.humano("2026-11-10T21:00", f"outra coisa {SENTINELA}")
    e = mede(pasta, resposta=r'source="chat"')["execucoes"][0]
    assert e["respondido"] is False and e["minutos_ate_resposta"] is None


def test_resposta_depois_da_proxima_rotina_nao_conta(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA)
    s.assistente("2026-11-10T20:01", "r1")
    s.meta("2026-11-11T08:00", TXT_ROTINA).assistente("2026-11-11T08:01", "r2")
    s.meta("2026-11-11T08:30", _canal("x", "completa"))
    r = mede(pasta, resposta=r'source="chat"')
    assert [e["respondido"] for e in r["execucoes"]] == [False, True]


def test_resposta_depois_do_ate_dentro_do_prazo(pasta):
    s = sessao(pasta, "s1").meta("2026-11-12T22:00", TXT_ROTINA)
    s.assistente("2026-11-12T22:01", "r1")
    s.meta("2026-11-13T09:00", _canal("x", "completa"))
    dentro = mede(pasta, resposta=r'source="chat"')["execucoes"][0]
    fora = mede(pasta, resposta=r'source="chat"', prazo_uso_h=6)["execucoes"][0]
    assert dentro["respondido"] is True and fora["respondido"] is False


def test_resposta_na_sessao_propria_excluida_nao_conta(pasta):
    # teste 1's error: the first count, 1, came from the measuring session itself
    sessao(pasta, "medindo").meta("2026-11-10T20:00", TXT_ROTINA) \
        .assistente("2026-11-10T20:01", "r1") \
        .humano("2026-11-10T21:00", 'grep source="chat" ' + SENTINELA)
    sem = mede(pasta, resposta=r'source="chat"')["execucoes"][0]
    com = mede(pasta, resposta=r'source="chat"',
               propria=("medindo", tr.para_utc("2026-11-10T20:30")))["execucoes"][0]
    assert sem["respondido"] is True  # the trap is real
    assert com["respondido"] is False


def test_sem_resposta_nem_acao_e_uso_indefinido(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA)
    s.assistente("2026-11-10T20:01", "r1")
    s.meta("2026-11-10T20:30", _canal("x", "completa"))
    e = mede(pasta)["execucoes"][0]
    assert e["uso_indefinido"] is True
    assert e["respondido"] is None and e["agido"] is None


def test_agido_por_comando_posterior(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA) \
        .assistente("2026-11-10T20:01", "r1")
    s.humano("2026-11-10T22:00").assistente(
        "2026-11-10T22:05", "r2", tool_uses=[tu("b1", command="tracker.py done 4")])
    e = mede(pasta, acoes=[r"comando:tracker\.py done"])["execucoes"][0]
    assert e["agido"] is True and e["minutos_ate_acao"] == 124.0  # from the run's end
    assert e["respondido"] is None and e["uso_indefinido"] is False
    nada = mede(pasta, acoes=[r"comando:tracker\.py offered"])["execucoes"][0]
    assert nada["agido"] is False


def test_acao_em_outra_sessao_nao_conta(pasta):
    sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA) \
        .assistente("2026-11-10T20:01", "r1")
    sessao(pasta, "s2").humano("2026-11-10T22:00").assistente(
        "2026-11-10T22:05", "r2", tool_uses=[tu("b1", command="tracker.py done 4")])
    e = mede(pasta, acoes=[r"comando:tracker\.py done"])["execucoes"][0]
    assert e["agido"] is False


def test_acao_no_ajudante_da_mesma_sessao_conta(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T20:00", TXT_ROTINA)
    s.assistente("2026-11-10T20:01", "r1")
    a = ajudante(pasta, "s1", "a1", meta={"agentType": "x"})
    a.primeiro_pedido("2026-11-10T21:00").assistente(
        "2026-11-10T21:01", "ra", tool_uses=[tu("b1", command="tracker.py done 4")])
    e = mede(pasta, acoes=[r"comando:tracker\.py done"])["execucoes"][0]
    assert e["agido"] is True


# ---------------------------------------------------------------- reviewer's findings, 15/11

TG = '^<channel source="plugin:chat'


def _tg(texto):
    return f'<channel source="plugin:chat" chat_id="1">{texto} {SENTINELA}</channel>'


def test_resposta_so_na_propria_sessao(pasta):
    s1 = sessao(pasta, "s1")
    s2 = sessao(pasta, "s2")
    s1.meta("2026-11-10T10:00", TXT_ROTINA).assistente("2026-11-10T10:01", "a1")
    s2.meta("2026-11-10T10:02", TXT_ROTINA).assistente("2026-11-10T10:03", "b1")
    s1.meta("2026-11-10T10:10", _tg("feito")).assistente("2026-11-10T10:11", "a2")
    r = mede(pasta, resposta=TG)
    assert [(e["sessao"], e["respondido"]) for e in r["execucoes"]] == [
        ("s1", True), ("s2", False)]


def test_proxima_corrida_de_outra_sessao_nao_corta_a_busca(pasta):
    s1 = sessao(pasta, "s1")
    s1.meta("2026-11-10T10:00", TXT_ROTINA).assistente("2026-11-10T10:01", "a1")
    sessao(pasta, "s2").meta("2026-11-10T10:02", TXT_ROTINA).assistente("2026-11-10T10:03", "b1")
    s1.humano("2026-11-10T10:20").assistente(
        "2026-11-10T10:21", "a2", tool_uses=[tu("x1", command="tracker.py done 1")])
    e = mede(pasta, acoes=[r"comando:tracker\.py done"])["execucoes"][0]
    assert e["sessao"] == "s1" and e["agido"] is True


def test_aviso_do_sistema_nao_e_resposta(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1")
    s.humano("2026-11-10T10:02", f"<task-notification> completa {SENTINELA}")
    s.assistente("2026-11-10T10:03", "r2")
    e = mede(pasta, resposta="completa")["execucoes"][0]
    assert e["respondido"] is False


def test_padroes_casados_e_aviso_de_padrao_que_nao_casa(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1",
                 tool_uses=[tu("b1", command="tracker.py done 1")])
    s.meta("2026-11-10T10:10", _tg("feito"))
    s.meta("2026-11-10T11:00", TXT_ROTINA).assistente("2026-11-10T11:01", "r2")
    bom = mede(pasta, fecha=r"comando:tracker", resposta=TG,
               acoes=[r"comando:tracker\.py done"])["regua"]
    assert bom["padroes_casados"] == {"abre": 2, "fecha": 1, "resposta": 1, "acao": [1]}
    assert not any("não casou" in a for a in bom["avisos"])
    ruim = mede(pasta, resposta='source="chat"',
                acoes=[r"comando:tracker\.py done", "comando:nada-disso"])["regua"]
    assert ruim["padroes_casados"] == {"abre": 2, "fecha": None, "resposta": 0,
                                       "acao": [1, 0]}
    assert ("o padrão de resposta não casou com nada na leitura: confira o padrão antes "
            "de dizer que não houve uso") in ruim["avisos"]
    assert sum("não casou" in a for a in ruim["avisos"]) == 2
    assert ruim["formato_mudou"] is False
    sem = mede(pasta)["regua"]
    assert sem["padroes_casados"] == {"abre": 2, "fecha": None, "resposta": None, "acao": []}
    assert not any("não casou" in a for a in sem["avisos"])


def test_comando_da_propria_rotina_nao_e_acao(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1",
                 tool_uses=[tu("b1", command="tracker.py offered 1")])
    dentro = mede(pasta, acoes=[r"comando:tracker\.py offered"])["execucoes"][0]
    assert dentro["agido"] is False
    s.humano("2026-11-10T10:30").assistente(
        "2026-11-10T10:31", "r2", tool_uses=[tu("b2", command="tracker.py offered 1")])
    depois = mede(pasta, acoes=[r"comando:tracker\.py offered"])["execucoes"][0]
    assert depois["agido"] is True and depois["minutos_ate_acao"] == 30.0


def test_mensagem_de_colega_no_meio_nao_fecha_e_primeiro_pedido_ainda_abre(pasta):
    sessao(pasta, "s1").humano("2026-11-10T09:00").assistente("2026-11-10T09:01", "r0")
    t = ajudante(pasta, "s1", "a1", meta={"teamName": "x", "customAgentType": "faq-extrator"})
    t.humano("2026-11-10T10:00",
             f'<teammate-message teammate_id="lead">Execute the job {SENTINELA}'
             '</teammate-message>')
    t.assistente("2026-11-10T10:01", "q1")
    t.humano("2026-11-10T10:02",
             '<teammate-message teammate_id="lead">status?</teammate-message>')
    t.assistente("2026-11-10T10:03", "q2").assistente("2026-11-10T10:04", "q3")
    [e] = mede(pasta, abre="texto:Execute the job")["execucoes"]
    assert e["agente"] == "a1" and e["largo"]["chamadas"] == 3


def test_nova_tentativa_com_exit_eco_zero(pasta):
    cmd = "faq.py confere; echo EXIT=$?"
    s = sessao(pasta, "s1").meta("2026-11-10T21:00", TXT_ROTINA)
    s.assistente("2026-11-10T21:01", "r1", tool_uses=[tu("b1", command=cmd)])
    s.resultado("2026-11-10T21:01:30", "b1", "boom\nEXIT=1")
    s.assistente("2026-11-10T21:02", "r2", tool_uses=[tu("b2", command=cmd)])
    s.resultado("2026-11-10T21:02:30", "b2", "certo\nEXIT=0")
    e = mede(pasta)["execucoes"][0]
    assert e["comandos"]["por_desfecho"] == {"saida_1": 1, "saida_0": 1}
    assert e["comandos"]["mais_de_uma_tentativa"] is True


def test_acordar_uma_vez_por_arquivo_e_corridas_seguintes_marcadas(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T08:00")
    s.assistente("2026-11-10T08:01", "r0", uso(1, 100000, 0, 1))
    for i, h in enumerate(["10", "11", "12"]):
        s.meta(f"2026-11-10T{h}:00", TXT_ROTINA)
        s.assistente(f"2026-11-10T{h}:01", f"r{i + 1}", uso(1, 0, 5000, 1))
    r = mede(pasta)
    assert r["totais"]["acordar"] == {"n": 1, "mediana": 100002, "min": 100002,
                                      "max": 100002}
    assert [("acordar_compartilhado" in e["sinais"]) for e in r["execucoes"]] == [
        True, True, True]  # every run opens after the session's first message


def test_primeira_corrida_do_arquivo_nao_e_compartilhada(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1", uso(1, 50, 0, 1))
    s.meta("2026-11-10T11:00", TXT_ROTINA).assistente("2026-11-10T11:01", "r2")
    s.meta("2026-11-10T12:00", TXT_ROTINA).assistente("2026-11-10T12:01", "r3")
    r = mede(pasta)
    assert [("acordar_compartilhado" in e["sinais"]) for e in r["execucoes"]] == [
        False, True, True]
    assert r["totais"]["acordar"]["n"] == 1 and r["totais"]["acordar"]["mediana"] == 52


# ---------------------------------------------------------------- privacy and totals


def test_sentinela_nunca_sai_e_totais_sobre_contexto_mais_escritos(pasta):
    s = sessao(pasta, "s1").meta("2026-11-10T10:00", TXT_ROTINA)
    s.assistente("2026-11-10T10:01", "r1", uso(1, 2, 3, 4), tool_uses=[
        tu("ag1", "Agent", subagent_type="x", prompt=SENTINELA), tu("b1")])
    s.resultado("2026-11-10T10:02", "b1")
    ajudante(pasta, "s1", "ax", meta={"toolUseId": "ag1"}) \
        .primeiro_pedido("2026-11-10T10:03").assistente("2026-11-10T10:04", "a1")
    s.meta("2026-11-11T10:00", TXT_ROTINA)
    s.assistente("2026-11-11T10:01", "r2", uso(10, 20, 30, 40))
    s.meta("2026-11-11T10:05", _canal("x", "ok"))
    r = mede(pasta, fecha="comando:echo", resposta="chat", acoes=["comando:echo"])
    assert SENTINELA not in json.dumps(r)
    assert r["totais"]["n"] == 2 and r["totais"]["numero"] == "contexto + escritos"
    # both runs share s1's one wake: counted once per file, not once per run
    assert r["totais"]["acordar"] == {"n": 1, "mediana": 10, "min": 10, "max": 10}
    assert r["totais"]["estreito"]["max"] == 100
