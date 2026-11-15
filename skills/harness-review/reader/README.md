# The transcript reader

Placeholder: the full manual replaces this file.
It holds only what `tests/test_docs.py` pins: the verb, every flag, the answer's keys and the glossary.

## The one verb: `mede.py execucoes`

```
python3 -B skills/harness-review/reader/mede.py execucoes --abre 'texto:^\[routine\] read queue/next\.md' --de 2026-11-01 --ate 2026-11-07 --sem-sessao-propria
```

### Flags

`--pasta`, `--de`, `--ate`, `--sessao-propria`, `--desde`, `--sem-sessao-propria`, `--exclui-sessao`, `--abre`, `--fecha`, `--resposta`, `--acao`, `--prazo-uso-h`, `--fuso`.

## The answer

- Top level: `execucoes`, `totais`, `regua`.
- `execucoes`: `sessao`, `agente`, `inicio`, `fim`, `sinais`, `estreito`, `largo`, `acordar`, `ajudantes`, `comandos`, `respondido`, `minutos_ate_resposta`, `agido`, `minutos_ate_acao`, `uso_indefinido`.
- Every cost block: `entrada`, `gravados`, `relidos`, `escritos`, `contexto`, `chamadas`.
- `comandos`: `por_desfecho`, `mais_de_uma_tentativa`.
- `totais`: `n`, `numero`, `estreito`, `largo`, `acordar`.
- `regua`: `fonte`, `regra_da_pasta`, `fuso`, `janela`, `medido_em`, `arquivos_lidos`, `linhas_lidas`, `linhas_ilegiveis`, `linhas_em_escrita`, `tipos_desconhecidos`, `excluidas`, `duplicadas_por_uuid`, `tipo_de_ajudante_por_fonte`, `padroes`, `padroes_casados`, `formato_mudou`, `avisos`.

## Glossary

| Name | Meaning |
|---|---|
| `--pasta` | the transcripts folder to read |
| `--de` | the window's start |
| `--ate` | the window's end |
| `--sessao-propria` | the id of the session doing the measuring |
| `--desde` | when the measuring session started |
| `--sem-sessao-propria` | no measuring session to leave out |
| `--exclui-sessao` | a whole session to leave out |
| `--abre` | what opens a run |
| `--fecha` | what closes a run |
| `--resposta` | a message that counts as a reply |
| `--acao` | a command that counts as acting on the result |
| `--prazo-uso-h` | hours to look for a reply or action |
| `--fuso` | the time zone to read and show times in |
| `execucoes` | runs |
| `totais` | totals |
| `regua` | ruler |
| `sessao` | session |
| `agente` | sub-agent id |
| `inicio` | start |
| `fim` | end |
| `sinais` | signals |
| `estreito` | narrow cost |
| `largo` | wide cost |
| `acordar` | wake cost |
| `ajudantes` | sub-agents |
| `comandos` | commands |
| `respondido` | replied |
| `minutos_ate_resposta` | minutes to reply |
| `agido` | acted on |
| `minutos_ate_acao` | minutes to action |
| `uso_indefinido` | use not defined |
| `entrada` | input tokens |
| `gravados` | cache-write tokens |
| `relidos` | cache-read tokens |
| `escritos` | output tokens |
| `contexto` | context tokens |
| `chamadas` | model calls |
| `por_desfecho` | by outcome |
| `mais_de_uma_tentativa` | more than one attempt |
| `n` | count |
| `numero` | the number the medians are over |
| `fonte` | source folder |
| `regra_da_pasta` | folder rule |
| `fuso` | time zone |
| `janela` | window |
| `medido_em` | measured at |
| `arquivos_lidos` | files read |
| `linhas_lidas` | lines read |
| `linhas_ilegiveis` | unreadable lines |
| `linhas_em_escrita` | lines still being written |
| `tipos_desconhecidos` | unknown record types |
| `excluidas` | excluded sessions |
| `duplicadas_por_uuid` | duplicates by uuid |
| `tipo_de_ajudante_por_fonte` | sub-agent type by source |
| `padroes` | patterns |
| `padroes_casados` | pattern match counts |
| `formato_mudou` | format changed |
| `avisos` | warnings |
