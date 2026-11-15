"""Core rules of transcritos.py, each with the case that must fail when the rule is removed."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fabrica import FUSO_TESTE, SENTINELA, ajudante, ids_fixos, sessao, tu, uso

import transcritos as tr


def le(pasta, de="2026-11-10", ate="2026-11-12", propria=None, excluidas=()):
    return tr.ler(pasta, tr.para_utc(de), tr.para_utc(ate, fim_do_dia=True), propria,
                  list(excluidas))


def chamadas_por_chave(leitura):
    return {c.chave: c for c in leitura.chamadas}


# ---------------------------------------------------------------- folder resolution


def test_pasta_padrao_cai_dentro_do_tmp(tmp_path, monkeypatch):
    atual = tmp_path / "meu proj"
    atual.mkdir()
    monkeypatch.chdir(atual)
    pasta, regra = tr.pasta_padrao()
    assert pasta.is_relative_to(tmp_path) and regra == "variavel"
    monkeypatch.delenv("IA_CODIGO_PROJETOS_DIR")
    assert tr.pasta_padrao() == (tmp_path / "config" / "projects"
                                 / tr.codifica_raiz(Path.cwd()), "pasta_atual")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    assert tr.pasta_padrao() == (tmp_path / "casa" / ".claude" / "projects"
                                 / tr.codifica_raiz(Path.cwd()), "pasta_atual")
    assert tr.pasta_padrao()[0].is_relative_to(tmp_path)


def test_pasta_padrao_variavel_depois_sessao_depois_pasta_atual(tmp_path, monkeypatch):
    atual = tmp_path / "meu proj"
    atual.mkdir()
    monkeypatch.chdir(atual)
    projetos = tmp_path / "config" / "projects"
    sessao(projetos / "-b-dono", "eu").humano("2026-11-10T10:00")
    (projetos / "-a-outro").mkdir()
    # the env folder wins even when the session's file exists elsewhere
    assert tr.pasta_padrao("eu")[1] == "variavel"
    monkeypatch.delenv("IA_CODIGO_PROJETOS_DIR")
    assert tr.pasta_padrao("eu") == (projetos / "-b-dono", "sessao_propria")
    # a session id whose file is in no project folder falls to the cwd rule
    assert tr.pasta_padrao("ninguem") == (projetos / tr.codifica_raiz(Path.cwd()),
                                          "pasta_atual")
    assert tr.pasta_padrao(None)[1] == "pasta_atual"


def test_codifica_raiz_com_espacos():
    assert tr.codifica_raiz(Path("/home/a b/my proj")) == "-home-a-b-my-proj"
    assert tr.codifica_raiz(Path("/home/zé/x.y")) == "-home-z--x-y"


def test_pasta_ausente(tmp_path):
    with pytest.raises(tr.PastaAusente):
        le(tmp_path / "nao-existe")


# ---------------------------------------------------------------- cold start


def test_pasta_vazia_responde_zeros_e_regua(pasta):
    r = le(pasta)
    assert r.chamadas == [] and r.aberturas == [] and r.ajudantes == []
    assert r.regua["arquivos_lidos"] == {"principais": 0, "ajudantes": 0}
    assert r.regua["linhas_lidas"] == 0
    assert r.regua["formato_mudou"] is False
    assert set(r.regua) == {
        "fonte", "janela", "medido_em", "arquivos_lidos", "linhas_lidas",
        "linhas_ilegiveis", "linhas_em_escrita", "tipos_desconhecidos", "excluidas",
        "duplicadas_por_uuid", "tipo_de_ajudante_por_fonte", "padroes", "padroes_casados",
        "formato_mudou", "avisos", "fuso", "regra_da_pasta"}
    assert r.regua["fuso"] == FUSO_TESTE and r.regua["regra_da_pasta"] == "pasta"
    assert r.regua["fonte"] == str(pasta.resolve())  # still the folder path
    assert r.regua["linhas_em_escrita"] == {}
    assert set(r.regua["tipo_de_ajudante_por_fonte"]) == set(tr.FONTES_DE_TIPO)
    assert r.regua["janela"] == {"de": "2026-11-10T00:00:00-05:00",
                                 "ate": "2026-11-12T23:59:59.999000-05:00"}


def test_uma_sessao_sem_pasta_de_ajudantes(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00").assistente("2026-11-10T10:01", "r1")
    r = le(pasta)
    assert len(r.sessoes) == 1 and len(r.chamadas) == 1 and len(r.aberturas) == 1
    assert r.ajudantes == []


def test_ajudante_sem_meta(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00")
    ajudante(pasta, "s1", "a0ff1925c2e55c63c", com_meta=False) \
        .primeiro_pedido("2026-11-10T10:01").assistente("2026-11-10T10:02", "r1")
    r = le(pasta)
    assert len(r.ajudantes) == 1
    assert r.ajudantes[0].tipo == "desconhecido"
    assert r.regua["tipo_de_ajudante_por_fonte"]["desconhecido"] == 1
    assert r.regua["formato_mudou"] is False


# ---------------------------------------------------------------- rule 5: API calls


def test_uma_resposta_em_tres_linhas_conta_uma_vez_com_max_e_tres_tool_uses(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00")
    s.assistente("2026-11-10T10:01", "r1", uso(10, 2, 3, 1), [tu("t1")])
    s.assistente("2026-11-10T10:01", "r1", uso(10, 2, 3, 50), [tu("t2")])
    s.assistente("2026-11-10T10:01", "r1", uso(10, 2, 3, 7), [tu("t3")])
    r = le(pasta)
    assert len(r.chamadas) == 1
    c = r.chamadas[0]
    assert c.uso == {"entrada": 10, "gravados": 2, "relidos": 3, "escritos": 50,
                     "contexto": 15}
    assert [t.id for t in c.tool_uses] == ["t1", "t2", "t3"]


def test_mesmo_request_id_em_dois_arquivos_conta_uma_vez(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00") \
        .assistente("2026-11-10T10:01", "r1", uso(escritos=5), [tu("t1")])
    sessao(pasta, "s2").humano("2026-11-10T11:00") \
        .assistente("2026-11-10T11:01", "r1", uso(escritos=9), [tu("t2")])
    r = le(pasta)
    assert len(r.chamadas) == 1
    c = r.chamadas[0]
    assert c.arquivo == "s1.jsonl" and c.uso["escritos"] == 9
    assert [t.id for t in c.tool_uses] == ["t1", "t2"]


def test_chave_por_msg_id_e_recuo_para_arquivo_uuid(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00")
    s.assistente("2026-11-10T10:01", None, msg_id="msg_01ABCDEFGHIJK", uuid="u1")
    s.assistente("2026-11-10T10:01", None, msg_id="msg_01ABCDEFGHIJK", uuid="u2")
    s.assistente("2026-11-10T10:02", None, msg_id="abc", uuid="u3")
    s.assistente("2026-11-10T10:02", None, msg_id="abc", uuid="u4")
    r = le(pasta)
    assert set(chamadas_por_chave(r)) == {"msg_01ABCDEFGHIJK", "s1.jsonl:u3", "s1.jsonl:u4"}


def test_sem_chave_nenhuma_conta_uma_vez_por_linha_com_aviso(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00")
    for _ in range(2):
        s.bruto({"type": "assistant", "timestamp": "2026-11-10T13:01:00.000Z",
                 "message": {"role": "assistant", "content": [], "usage": uso()}})
    r = le(pasta)
    assert len(r.chamadas) == 2
    assert any("sem requestId" in a for a in r.regua["avisos"])


# ---------------------------------------------------------------- rules 1, 3: order, dedupe


def test_uuid_repetido_em_segundo_arquivo_conta_uma_vez(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00", uuid="u1") \
        .assistente("2026-11-10T10:01", "r1", uuid="u2")
    sessao(pasta, "s2").humano("2026-11-10T10:00", uuid="u1") \
        .humano("2026-11-10T12:00")
    r = le(pasta)
    assert r.regua["duplicadas_por_uuid"] == 1
    assert [a.arquivo for a in r.aberturas] == ["s1.jsonl", "s2.jsonl"]


def test_arquivos_escritos_ao_contrario_mantem_entrada_no_mais_antigo(pasta):
    # "a" is written first and sorts first by name, but its first entry is later.
    sessao(pasta, "a").humano("2026-11-11T09:00", uuid="ux") \
        .humano("2026-11-11T09:05")
    sessao(pasta, "b").humano("2026-11-10T09:00").humano("2026-11-11T09:00", uuid="ux")
    r = le(pasta)
    dono = [a.arquivo for a in r.aberturas if a.timestamp == tr.para_utc("2026-11-11T09:00")]
    assert dono == ["b.jsonl"]
    assert [a.nome for a in r.arquivos] == ["b.jsonl", "a.jsonl"]


def test_ajudante_aninhado_conta_uma_vez_e_vem_depois_do_pai(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00") \
        .assistente("2026-11-10T10:01", "r0", tool_uses=[
            tu("tp", "Agent", subagent_type="opus-medium", prompt=SENTINELA)])
    pai = ajudante(pasta, "s1", "bpai", meta={"agentType": "x", "toolUseId": "tp"})
    pai.primeiro_pedido("2026-11-10T10:02").humano("2026-11-10T10:03", uuid="ufork")
    pai.assistente("2026-11-10T10:04", "r1", tool_uses=[
        tu("tf", "Agent", subagent_type="general-purpose")])
    # the child's name sorts first and it replays the parent's entry at the same moment
    filho = ajudante(pasta, "s1", "afilho",
                     meta={"agentType": "y", "toolUseId": "tf", "parentAgentId": "bpai"})
    filho.humano("2026-11-10T10:02").humano("2026-11-10T10:03", uuid="ufork")
    filho.assistente("2026-11-10T10:05", "r2")
    r = le(pasta)
    assert [a.agente for a in r.ajudantes] == ["bpai", "afilho"]
    filho_aj = r.ajudantes[1]
    assert filho_aj.parent_agent_id == "bpai" and filho_aj.tipo == "general-purpose"
    assert r.regua["duplicadas_por_uuid"] == 1
    assert len(r.chamadas) == 3


# ---------------------------------------------------------------- rule 2: unreadable


def test_linha_ilegivel_contada_e_resto_lido(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00")
    s.linha_quebrada()
    s.humano("2026-11-10T10:05")
    r = le(pasta)
    assert r.regua["linhas_ilegiveis"] == {"s1.jsonl": 1}
    assert len(r.aberturas) == 2
    assert r.regua["formato_mudou"] is True
    assert r.regua["linhas_em_escrita"] == {}


def test_ultima_linha_ainda_sendo_escrita_nao_muda_formato(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00").assistente("2026-11-10T10:01", "r1")
    s.linha_cortada()
    r = le(pasta)
    assert r.regua["linhas_em_escrita"] == {"s1.jsonl": 1}
    assert r.regua["linhas_ilegiveis"] == {}
    assert r.regua["formato_mudou"] is False
    assert len(r.chamadas) == 1


def test_linha_quebrada_no_meio_e_cortada_no_fim(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00").linha_quebrada()
    s.humano("2026-11-10T10:05").linha_cortada()
    r = le(pasta)
    assert r.regua["linhas_ilegiveis"] == {"s1.jsonl": 1}
    assert r.regua["linhas_em_escrita"] == {"s1.jsonl": 1}
    assert r.regua["formato_mudou"] is True


# ---------------------------------------------------------------- rules 6, 7: openers


def test_abertura_is_meta_fica_com_origem_meta(pasta):
    sessao(pasta, "s1").meta("2026-11-10T10:00").humano("2026-11-10T10:01", blocos=True)
    r = le(pasta)
    assert [a.origem for a in r.aberturas] == ["meta", "humano"]


def test_aviso_de_ajudante_sem_is_meta_fica_com_origem_meta(pasta):
    """Real shape (07/11-15/11): a sub-agent notice is a user line without ``isMeta``."""
    sessao(pasta, "s1").humano("2026-11-10T10:00", f"  <task-notification> {SENTINELA}") \
        .humano("2026-11-10T10:01", f"[routine] {SENTINELA}")
    r = le(pasta)
    assert [a.origem for a in r.aberturas] == ["meta", "humano"]


@pytest.mark.parametrize("aviso", [
    f'<teammate-message teammate_id="lead">status? {SENTINELA}</teammate-message>',
    f"<local-command-stdout>{SENTINELA}</local-command-stdout>",
])
def test_mensagem_de_colega_e_saida_de_comando_local_sao_meta(pasta, aviso):
    sessao(pasta, "s1").humano("2026-11-10T10:00", aviso)
    assert [a.origem for a in le(pasta).aberturas] == ["meta"]


def test_comando_digitado_tem_origem_comando(pasta):
    sessao(pasta, "s1").comando("2026-11-10T10:00", "/my-tasks")
    r = le(pasta)
    assert len(r.aberturas) == 1
    assert r.aberturas[0].origem == "comando" and r.aberturas[0].comando == "my-tasks"


def test_primeiro_pedido_do_ajudante_e_abertura_do_arquivo_dele(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00")
    ajudante(pasta, "s1", "a1", meta={"agentType": "Explore"}) \
        .primeiro_pedido("2026-11-10T10:01")
    r = le(pasta)
    sub = [a for a in r.aberturas if a.agente == "a1"]
    assert len(sub) == 1 and sub[0].arquivo == "s1/subagents/agent-a1.jsonl"


def test_nunca_turno_blob_compacto_resultado_interrupcao(pasta):
    sessao(pasta, "s1").api_request_blob("2026-11-10T10:00").compacta("2026-11-10T10:01") \
        .resultado("2026-11-10T10:02", "t1").interrompe("2026-11-10T10:03") \
        .tipo("2026-11-10T10:04", "system")
    r = le(pasta)
    assert r.aberturas == [] and r.chamadas == []


# ---------------------------------------------------------------- rule 8: sub-agent type


@pytest.mark.parametrize("meta,arquivo,tipo,fonte", [
    ({"customAgentType": "c", "spawnedAgentType": "s", "agentType": "a",
      "toolUseId": "tp", "teamName": "eq"}, "a1", "c", "customAgentType"),
    ({"spawnedAgentType": "s", "agentType": "a", "toolUseId": "tp", "teamName": "eq"},
     "a1", "s", "spawnedAgentType"),
    ({"agentType": "a", "toolUseId": "tp"}, "a1", "opus-high", "subagent_type_do_pai"),
    ({"agentType": "a", "toolUseId": "outro"}, "a1", "a", "agentType"),
    ({}, "aregua-juiz-836c035b2ce58000", "regua-juiz", "nome_do_arquivo"),
    ({}, "a0ff1925c2e55c63c", "desconhecido", "desconhecido"),
])
def test_tipo_do_ajudante_seis_ramos(pasta, meta, arquivo, tipo, fonte):
    sessao(pasta, "s1").humano("2026-11-10T10:00").assistente(
        "2026-11-10T10:01", "r0", tool_uses=[tu("tp", "Agent", subagent_type="opus-high")])
    ajudante(pasta, "s1", arquivo, meta=meta).primeiro_pedido("2026-11-10T10:02")
    r = le(pasta)
    assert (r.ajudantes[0].tipo, r.ajudantes[0].fonte_do_tipo) == (tipo, fonte)
    assert r.regua["tipo_de_ajudante_por_fonte"][fonte] == 1
    assert sum(r.regua["tipo_de_ajudante_por_fonte"].values()) == 1
    assert r.regua["formato_mudou"] is False


def test_ajudante_de_equipe_sem_tipo_proprio_muda_formato(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00")
    ajudante(pasta, "s1", "a1", meta={"agentType": "x", "teamName": "eq"}) \
        .primeiro_pedido("2026-11-10T10:02")
    r = le(pasta)
    assert r.regua["formato_mudou"] is True
    assert any("equipe" in a for a in r.regua["avisos"])


# ---------------------------------------------------------------- rule 9: outcomes


def _um_resultado(pasta, texto, is_error=False, tur=None, comando="ls", blocos=False):
    sessao(pasta, "s1").humano("2026-11-10T10:00").assistente(
        "2026-11-10T10:01", "r1", tool_uses=[tu("t1", command=comando)]) \
        .resultado("2026-11-10T10:02", "t1", texto, is_error, tur, blocos)
    return le(pasta).resultados["t1"]


@pytest.mark.parametrize("tur", [
    {"stdout": "x", "interrupted": False}, [{"type": "text", "text": "x"}], "x"])
def test_tool_use_result_dict_lista_texto(pasta, tur):
    assert _um_resultado(pasta, "x", tur=tur) == "ok"


def test_texto_vazio_usa_tool_use_result_texto(pasta):
    assert _um_resultado(pasta, "", True, "PreToolUse:Bash negado") == "negado_por_gancho"


def test_exit_code_1(pasta):
    assert _um_resultado(pasta, "Exit code 1\nfalhou", True) == "saida_1"


def test_exit_code_0_em_texto(pasta):
    assert _um_resultado(pasta, "Exit code 0", False) == "saida_0"


def test_exit_code_dentro_de_error(pasta):
    assert _um_resultado(pasta, "<error>Exit code 2\nx</error>", True,
                         blocos=True) == "saida_2"


def test_negado_por_gancho_nao_e_erro(pasta):
    assert _um_resultado(pasta, "PreToolUse:Bash hook error: bloqueado", True) \
        == "negado_por_gancho"


def test_sucesso_que_comeca_com_hook_fica_ok(pasta):
    assert _um_resultado(pasta, "hooks instalados em .claude", False) == "ok"


def test_erro_sem_codigo(pasta):
    assert _um_resultado(pasta, "falhou", True) == "erro"


def test_exit_eco_so_com_exit_no_comando(pasta, tmp_path):
    assert _um_resultado(pasta, "x\nEXIT=3", False, comando='faz; echo "EXIT=$?"') \
        == "saida_3"


def test_exit_eco_sem_exit_no_comando_fica_ok(pasta):
    assert _um_resultado(pasta, "x\nEXIT=3", False, comando="cat log") == "ok"


def test_interrompido(pasta):
    assert _um_resultado(pasta, "x", False, {"stdout": "", "interrupted": True}) \
        == "interrompido"


def test_resultado_em_arquivo_de_ajudante(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00")
    ajudante(pasta, "s1", "a1", meta={"agentType": "x"}).primeiro_pedido("2026-11-10T10:01") \
        .assistente("2026-11-10T10:02", "r1", tool_uses=[tu("t9")]) \
        .resultado("2026-11-10T10:03", "t9", "Exit code 4", True)
    assert le(pasta).resultados["t9"] == "saida_4"


# ---------------------------------------------------------------- rule 10: whole command


def test_comando_longo_inteiro(pasta):
    comando = "x" * 5000 + " FIM-DO-COMANDO"
    sessao(pasta, "s1").humano("2026-11-10T10:00").assistente(
        "2026-11-10T10:01", "r1", tool_uses=[tu("t1", command=comando)])
    cmd = le(pasta).chamadas[0].tool_uses[0].input["command"]
    assert len(cmd) == 5015 and cmd.endswith("FIM-DO-COMANDO")


# ---------------------------------------------------------------- rule 4: window


def test_bordas_da_janela_em_menos_cinco():
    assert tr.para_utc("2026-11-10") == datetime(2026, 11, 10, 5, tzinfo=timezone.utc)
    assert tr.para_utc("2026-11-10T21:30") == datetime(2026, 11, 11, 2, 30,
                                                       tzinfo=timezone.utc)
    assert tr.para_utc("2026-11-12", fim_do_dia=True) == datetime(
        2026, 11, 13, 4, 59, 59, 999000, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        tr.para_utc("10/11/2026")


def test_arquivo_fora_da_janela_nao_entra_e_borda_entra(pasta):
    sessao(pasta, "antes").humano("2026-11-09T23:59")
    sessao(pasta, "borda").humano("2026-11-10T00:00")
    sessao(pasta, "fim").humano("2026-11-12T23:59:59")
    sessao(pasta, "depois").humano("2026-11-13T00:00")
    r = le(pasta)
    assert sorted(s.id for s in r.sessoes) == ["borda", "fim"]


def test_arquivo_com_entradas_antes_e_depois_lido_inteiro(pasta):
    sessao(pasta, "s1").humano("2026-11-01T10:00").humano("2026-11-11T10:00") \
        .humano("2026-11-20T10:00")
    r = le(pasta)
    assert len(r.aberturas) == 3


def test_ajudante_julgado_pelo_proprio_horario(pasta):
    sessao(pasta, "s1").humano("2026-11-01T10:00")
    ajudante(pasta, "s1", "a1", meta={"agentType": "x"}).primeiro_pedido("2026-11-11T10:00")
    r = le(pasta)
    assert r.sessoes == [] and [a.agente for a in r.ajudantes] == ["a1"]
    assert r.ajudantes[0].sessao == "s1"


# ---------------------------------------------------------------- own session, exclusions


def test_sessao_propria_excluida_so_desde(pasta):
    desde = tr.para_utc("2026-11-11T10:00")
    sessao(pasta, "eu").humano("2026-11-11T09:00").assistente("2026-11-11T09:01", "r1") \
        .humano("2026-11-11T10:00").assistente("2026-11-11T10:01", "r2")
    ajudante(pasta, "eu", "depois", meta={"agentType": "x"}) \
        .primeiro_pedido("2026-11-11T10:02").assistente("2026-11-11T10:03", "r3")
    r = le(pasta, propria=("eu", desde))
    assert set(chamadas_por_chave(r)) == {"r1"}
    assert len(r.aberturas) == 1 and r.ajudantes == []
    assert r.regua["excluidas"] == ["eu desde 2026-11-11T10:00:00-05:00"]


def test_ajudante_da_propria_que_comecou_antes_fica(pasta):
    desde = tr.para_utc("2026-11-11T10:00")
    sessao(pasta, "eu").humano("2026-11-11T09:00")
    ajudante(pasta, "eu", "a1", meta={"agentType": "x"}) \
        .primeiro_pedido("2026-11-11T09:59:58").assistente("2026-11-11T10:05", "r9")
    r = le(pasta, propria=("eu", desde))
    assert [a.agente for a in r.ajudantes] == ["a1"]
    assert "r9" in chamadas_por_chave(r)


def test_sessao_excluida_inteira_com_ajudantes(pasta):
    sessao(pasta, "fora").humano("2026-11-11T09:00")
    ajudante(pasta, "fora", "a1", meta={"agentType": "x"}).primeiro_pedido("2026-11-11T09:01")
    sessao(pasta, "dentro").humano("2026-11-11T09:00")
    r = le(pasta, excluidas=["fora"])
    assert [s.id for s in r.sessoes] == ["dentro"] and r.ajudantes == []
    assert r.regua["excluidas"] == ["fora"]


# ---------------------------------------------------------------- format check


def test_tipo_desconhecido_informa_sem_mudar_formato(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00").tipo("2026-11-10T10:01", "novo-tipo") \
        .assistente("2026-11-10T10:02", "r1")
    r = le(pasta)
    assert r.regua["tipos_desconhecidos"] == {"novo-tipo": 1}
    assert r.regua["formato_mudou"] is False


def test_assistente_sem_uso_muda_formato(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00") \
        .assistente("2026-11-10T10:01", "r1", sem_uso=True)
    r = le(pasta)
    assert r.regua["formato_mudou"] is True and r.chamadas == []


# ---------------------------------------------------------------- rule 11: privacy (core)


def test_regua_e_registros_sem_conteudo(pasta):
    s = sessao(pasta, "s1").humano("2026-11-10T10:00").comando("2026-11-10T10:01", "x")
    s.assistente("2026-11-10T10:02", "r1", tool_uses=[tu("t1")]) \
        .resultado("2026-11-10T10:03", "t1", is_error=True).linha_quebrada()
    ajudante(pasta, "s1", "a1", meta={"teamName": "eq"}).primeiro_pedido("2026-11-10T10:04")
    r = le(pasta, propria=("s9", tr.para_utc("2026-11-12")))
    assert SENTINELA not in json.dumps(r.regua)
    assert SENTINELA not in repr(r.ajudantes) + repr(r.chamadas) + repr(r.aberturas)
    assert SENTINELA not in json.dumps(r.resultados)
    assert r.aberturas[0].texto.endswith(SENTINELA)  # kept in memory for matching


def test_medido_em_no_fuso_de_teste(pasta):
    medido = datetime.fromisoformat(le(pasta).regua["medido_em"])
    assert medido.utcoffset() == datetime.now(ZoneInfo(FUSO_TESTE)).utcoffset()


# ---------------------------------------------------------------- the zone (rule 12)


@pytest.fixture
def tz_do_computador():
    """Set the process's own zone through TZ, and put it back (and re-read it) after."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is POSIX only")
    antes = os.environ.get("TZ")

    def muda(nome: str) -> None:
        os.environ["TZ"] = nome
        time.tzset()
        tr.define_fuso(None)

    yield muda
    if antes is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = antes
    time.tzset()


@pytest.mark.parametrize("zona", ["Asia/Kolkata", "America/New_York", "UTC"])
def test_sem_fuso_usa_as_regras_do_computador(pasta, tz_do_computador, zona):
    tz_do_computador(zona)
    esperado = datetime(2026, 11, 10, 21, 30).astimezone(timezone.utc)
    assert tr.para_utc("2026-11-10T21:30") == esperado
    assert tr.hora_local(esperado) == esperado.astimezone().isoformat()
    r = le(pasta)
    assert r.regua["fuso"] == "local"
    assert r.regua["janela"]["de"] == datetime(2026, 11, 10).astimezone().isoformat()
    medido = datetime.fromisoformat(r.regua["medido_em"])
    assert medido.utcoffset() == datetime.now().astimezone().utcoffset()


def test_lacuna_do_horario_de_verao_nos_dois_caminhos(tz_do_computador):
    """02:30 on 2026-03-08 does not exist in New York. zoneinfo with fold=0 reads it as 02:30
    at the old offset (07:30 UTC), always. The machine's rules are whatever the C library
    under this Python says (``astimezone()`` on the naive time): measured 15/11 on one Mac,
    Python 3.9 and 3.11 gave 01:30 EST (06:30 UTC) and a standalone 3.12 build gave 07:30
    UTC. So the two paths can differ by one hour inside a gap, never more."""
    tz_do_computador("America/New_York")
    maquina = tr.para_utc("2026-03-08T02:30")
    assert maquina == datetime(2026, 3, 8, 2, 30).astimezone(timezone.utc)
    assert maquina in (datetime(2026, 3, 8, 6, 30, tzinfo=timezone.utc),
                       datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc))
    tr.define_fuso("America/New_York")
    zona = tr.para_utc("2026-03-08T02:30")
    assert zona == datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc)
    # outside the gap the two paths agree, across the DST change too
    for t in ("2026-03-08T01:59", "2026-03-08T03:00", "2026-11-10T10:00"):
        tr.define_fuso(None)
        a = tr.para_utc(t)
        tr.define_fuso("America/New_York")
        assert a == tr.para_utc(t), t


@pytest.mark.parametrize("nome", ["Nao/Existe", "", "../etc"])
def test_define_fuso_recusa_nome_desconhecido(nome):
    with pytest.raises(ValueError, match="--fuso"):
        tr.define_fuso(nome)


def test_ids_fixos_escrevem_os_mesmos_bytes(tmp_path):
    def historia(p):
        sessao(p, "s1").humano("2026-11-10T10:00", "oi").assistente("2026-11-10T10:01", "r1")
        return (p / "s1.jsonl").read_bytes()

    with ids_fixos():
        um = historia(tmp_path / "um")
    with ids_fixos():
        dois = historia(tmp_path / "dois")
    tres = historia(tmp_path / "tres")
    assert um == dois and b"00000000-0000-4000-8000-000000000001" in um
    assert tres != um  # outside it the uuids are random again


@pytest.mark.parametrize("texto,esperado", [
    ("2026-11-10T13:01:00.000Z", datetime(2026, 11, 10, 13, 1, tzinfo=timezone.utc)),
    ("2026-11-10T13:01:00Z", datetime(2026, 11, 10, 13, 1, tzinfo=timezone.utc)),
    ("2026-11-10T13:01:00.000+00:00", datetime(2026, 11, 10, 13, 1, tzinfo=timezone.utc)),
    ("2026-11-10T13:01:00", datetime(2026, 11, 10, 13, 1, tzinfo=timezone.utc)),
    ("ontem", None),
    (17, None),
])
def test_hora_com_z_lida_em_todo_python(texto, esperado):
    """The real files end in "Z", which fromisoformat reads only from Python 3.11."""
    assert tr._ts(texto) == esperado


def test_hora_ilegivel_muda_formato_mesmo_fora_da_janela(pasta):
    sessao(pasta, "s1").humano("2026-11-10T10:00")
    sessao(pasta, "s2").bruto({"type": "user", "timestamp": "ontem", "uuid": "x",
                               "message": {"role": "user", "content": "oi"}})
    r = le(pasta)
    assert [s.id for s in r.sessoes] == ["s1"]  # s2 has no entry in the window
    assert r.regua["formato_mudou"] is True
    assert any("hora(s) ilegível(is) em s2.jsonl" in a for a in r.regua["avisos"])
    sessao(pasta, "s3").humano("2026-11-10T11:00")
    (pasta / "s2.jsonl").unlink()
    assert le(pasta).regua["formato_mudou"] is False  # the alarm is that file's, not noise


def test_regra_da_pasta_ecoada(pasta):
    assert tr.ler(pasta, tr.para_utc("2026-11-10"), tr.para_utc("2026-11-12"), None, [],
                  "sessao_propria").regua["regra_da_pasta"] == "sessao_propria"
