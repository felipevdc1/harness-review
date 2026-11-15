# The transcript reader

This folder holds the reader the harness-review skill takes every transcript number from.
It is read-only and model-free: it opens Claude Code's recorded conversations for reading, line by line, writes nothing, starts no model and calls no network.
It answers one question: the runs of one routine or skill in a time window, what each one cost, and whether its result was used.

Files: `transcritos.py` (the parsing core), `execucoes.py` (the one question), `mede.py` (the command line); the tests live in the package's `tests/` folder.
Each module's docstring is its API.
Standard library only.

The flags and the JSON keys are in Portuguese on purpose: the model is the reader's main user, and the names stay stable so old answers compare byte for byte with new ones.
The [Glossary](#glossary) at the end gives every flag and every key its meaning in English.
Error messages on stderr are Portuguese too; each one is a single plain sentence naming what to fix.

## The one verb: `mede.py execucoes`

From inside the skill, call it as `python3 -B "${CLAUDE_SKILL_DIR}/reader/mede.py" execucoes …`; from a clone of the package, as `python3 -B skills/harness-review/reader/mede.py execucoes …`.
On Windows, `python` instead of `python3`.

Example 1, a chat routine.
A routine is started by a line `[routine] read queue/next.md` in an always-on session; its result is used when the person replies on the chat channel or runs the queue's `done` command.
Each `[routine]` line opens one run; the measuring session is left out from the moment it started:

```
python3 -B skills/harness-review/reader/mede.py execucoes \
  --abre 'texto:^\[routine\] read queue/next\.md' \
  --de 2026-11-01 --ate 2026-11-07 \
  --sessao-propria "$CLAUDE_CODE_SESSION_ID" --desde 2026-11-08T09:30 \
  --resposta '^<channel source="plugin:chat' \
  --acao 'comando:queue\.py done'
```

Example 2, a skill.
A skill `nightly-notes` writes a notes file and ends with its `publish` command; its result is used when someone later runs `notes.py open`.
A run opens at each `Skill` call (or typed `/nightly-notes`) and stretches to the last `publish`; one earlier session that only tested the skill is left out whole, and times are read in New York time:

```
python3 -B skills/harness-review/reader/mede.py execucoes \
  --abre skill:nightly-notes \
  --fecha 'comando:notes\.py publish' \
  --acao 'comando:notes\.py open' --prazo-uso-h 12 \
  --de 2026-11-01 --ate 2026-11-07T18:00 --fuso America/New_York \
  --sem-sessao-propria --exclui-sessao 00000000-0000-4000-8000-000000000001
```

### Flags

- `--pasta <dir>`: the transcripts folder.
  Without it, the folder is picked by the first rule that applies, and `regua.regra_da_pasta` says which one did:
  1. `variavel`: the environment variable `IA_CODIGO_PROJETOS_DIR`, taken as the whole folder;
  2. `sessao_propria`: with `--sessao-propria`, the folder under `<config>/projects/` that holds `<session id>.jsonl`, so the reader finds the measuring session's own project wherever it is started from;
  3. `pasta_atual`: `<config>/projects/<encoded current folder>`, where every character of the current folder's path outside `A-Za-z0-9` becomes `-` (the rule Claude Code uses for its per-project folders).

  `<config>` is `$CLAUDE_CONFIG_DIR`, else `~/.claude`.
  With `--pasta` given, `regra_da_pasta` is `pasta`.
- `--de <YYYY-MM-DD[THH:MM]>` (required): the window's start, in local time.
- `--ate <YYYY-MM-DD[THH:MM]>` (required): the window's end, in local time; a date alone means the end of that day.
  There is no default window, so the answer always says which window was read.
- `--fuso <IANA zone>`: the zone every local time is read and shown in (`--de`, `--ate`, `--desde`, and every `inicio` and `fim` of the answer), for example `America/New_York`; `regua.fuso` names it.
  Without it, local times follow the machine's own rules and `regua.fuso` is `local`.
  The two agree everywhere except for a local time inside a daylight-saving gap (a clock time that does not exist that day): there the machine's result can differ by up to one hour from `--fuso`, depending on the Python build.
  Pass `--fuso` when the window's edges fall on a clock change, or when the answer must not depend on the machine.
  An unknown zone name is exit 2.
- `--sessao-propria <session id>` with `--desde <time>`: the session doing the measuring and when it started.
  Its entries from `--desde` on, and its sub-agent files whose first entry is from `--desde` on, are left out; its earlier entries are kept.
  A leading `claude:` on the id is stripped.
  `--desde` takes `YYYY-MM-DDTHH:MM` in local time (or `--fuso`), or a full ISO time with its offset (`2026-11-08T09:30:00-05:00`).
  The reader never reads the session id from the environment on its own; the caller passes it.
- `--sem-sessao-propria`: no session of this measurement to leave out.
  Exactly one of the two forms is required; otherwise the answer is exit 2 with the sentence "diga qual é a sessão desta medição e quando ela começou (--sessao-propria … --desde …) ou --sem-sessao-propria".
  The guard exists because a measuring session read without it counts its own calls into the numbers it reports.
- `--exclui-sessao <id>` (repeatable): a whole session to leave out, main file and sub-agents (for example the session that dispatched this review, or a test session).
- `--abre <pattern>` (required): what opens a run.
  `skill:<name>` is a `Skill` call with that name or a typed `/<name>` command (both in the same turn open one run, not two); `texto:<regex>` is a message line (any origin, main or sub-agent file) whose text matches; `comando:<regex>` is a Bash call whose whole command matches.
- `--fecha <pattern>`: `texto:<regex>` or `comando:<regex>`; the run stretches to the last match before the next opening in the same file.
  Without it, a run ends before the next human message or the next opening in the same file, else at the file's end.
- `--resposta <regex>`: a later message line in the run's own file (any origin, so chat-channel replies count) that counts as the result being used.
  System notices (sub-agent notices, teammate messages, local command output) and a sub-agent's first prompt never count.
  Minutes to the reply are counted from the run's opening.
- `--acao <comando:regex>` (repeatable): a Bash command in the run's session (its main file and that session's sub-agent files), strictly after the run's last event, that counts as the result being acted on.
  The routine's own commands therefore never count as the person's action; minutes to the action are counted from the run's end.
- `--prazo-uso-h <hours>` (default 24): how long after a run's opening a reply or action still counts.
  The lookup also stops at the next run of the same `--abre` in the same file.

## The answer

One JSON object on stdout (UTF-8, sorted keys), exit 0, even when the ruler carries warnings.
Exit 2 for bad arguments (a missing own-session form, a bad date, a bad pattern, an unknown `--fuso`) or a missing folder, with one plain Portuguese sentence on stderr and nothing on stdout; never a traceback, never a partial answer.
An empty folder is a valid answer with no runs.

- Top level: `execucoes`, `totais`, `regua`.
- `execucoes`: one entry per run, in time order: `sessao`, `agente` (null in a main file), `inicio`, `fim` (local time, or `--fuso`), `sinais`, `estreito`, `largo`, `acordar`, `ajudantes`, `comandos`, `respondido`, `minutos_ate_resposta`, `agido`, `minutos_ate_acao`, `uso_indefinido`.
- Every cost block carries `entrada` (`input_tokens`), `gravados` (`cache_creation_input_tokens`), `relidos` (`cache_read_input_tokens`), `escritos` (`output_tokens`), `contexto` (entrada + gravados + relidos) and `chamadas`.
- `estreito` is the narrow cost (the opening's call, for a message the first call after it, plus each closing match's call and the call after that one); `largo` is the wide cost (every call of the run plus the sub-agents it launched, nested ones included); `acordar` is the wake cost (the first call of the run's file).
  In an always-on session every run carries the same `acordar`, the session's one wake; quote `totais.acordar` (once per file) as the wake cost, never a run's own value.
- `ajudantes`: the run's sub-agents per resolved type, with `quantos`, `chamadas`, the usage split, `modelos` and their own `acordar`, kept apart from the main one.
- `comandos`: the run's Bash calls counted `por_desfecho` (`ok`, `erro`, `saida_N`, `negado_por_gancho`, `interrompido`, `sem_resultado`) and `mais_de_uma_tentativa` (the same command failed, then ended `ok` or `saida_0` inside the run).
- `respondido` and `agido` are true or false when `--resposta` or `--acao` was given; without both, every run is `uso_indefinido`, and `respondido` and `agido` are null, never true.
- `sinais`: any of `corta_janela` (opens inside the window, ends after it), `sessao_comecou_antes` (the file's first call is before the window, so its wake is not this run's), `atribuido_por_hora` (a teammate sub-agent added by time, not by its launching call), `acordar_compartilhado` (the run's opening is not the first message or call of its file, so its `acordar` is shared, not its own).
- `totais`: `n` (the number of runs), `numero` (which number the medians are over: `contexto + escritos`, every token the calls read or wrote), for `estreito` and `largo` the `n`, `mediana`, `min` and `max` over one number per run, and for `acordar` the same four over one number per file that holds a run (its first call, counted once), so `totais.acordar.n` counts files, not runs.
- `regua` (the ruler): `fonte`, `regra_da_pasta`, `fuso`, `janela`, `medido_em`, `arquivos_lidos`, `linhas_lidas`, `linhas_ilegiveis`, `linhas_em_escrita`, `tipos_desconhecidos`, `excluidas`, `duplicadas_por_uuid`, `tipo_de_ajudante_por_fonte`, `padroes`, `padroes_casados`, `formato_mudou`, `avisos`.
  `fonte` is the folder read, `regra_da_pasta` the rule that picked it (`pasta`, `variavel`, `sessao_propria` or `pasta_atual`), and `fuso` the zone's name or `local`.
  `formato_mudou: true` is the only stop signal (a file with model answers but no usage, a teammate sub-agent with no type of its own, or an unreadable line), explained in `avisos`; unknown record types are information only.
  `linhas_em_escrita` counts, per file, an unreadable last line with no newline (a line still being written, usually the measuring session's own); it is not a format change.
  `padroes_casados` says how many messages or commands each pattern matched anywhere in the reading (`abre`, `fecha`, `resposta`, and one count per `acao`); a `resposta` or `acao` count of 0 adds an `avisos` line, because it means the pattern is wrong and use was not measured, never that nothing was used.
  `padroes_casados.abre` can be larger than `totais.n`: it counts every match in the reading, including matches before `--de` or after `--ate` in the files read whole, and for `skill:` a call in the same turn as its typed command, which opens one run, not two; the step's frequency is `totais.n`, the number of runs.

## The traps it handles

1. Main files are read before sub-agent files, in a fixed order (first timestamp, then name; a nested sub-agent after its parent), so a replayed entry is kept by the earliest file.
2. An unreadable line is counted per file in the ruler, never raised and never silently skipped; a half-written last line is counted apart, in `linhas_em_escrita`.
3. An entry whose `uuid` was already seen is skipped and counted.
4. The window decides only which runs open: a file with any entry in the window is read whole, and a run's end, reply and wake may fall outside it.
   Files last modified before `--de` are not opened (they cannot hold an entry in the window).
5. A model call is counted once per `requestId` (else a long `msg_0…` id, else file and uuid), across files on purpose, keeping the largest output, and every tool call of every line of that answer is kept.
6. Only `user` and `assistant` lines are turns; compaction summaries and request records never are.
7. Message lines open turns with their origin: `humano`, `meta` (chat-channel messages, sub-agent notices, Stop-hook feedback) or `comando` (a typed slash command); a `meta` line never ends a run by itself.
   A sub-agent notice (`<task-notification`), a teammate message (`<teammate-message`) and a local command's output (`<local-command-stdout`) are recorded without `isMeta`, so the reader makes them `meta` by their opening text.
   A scheduled trigger line such as `[routine] read queue/next.md` is usually recorded without `isMeta` too and stays `humano`, so it ends the previous run as the next `--abre` match.
   A `texto:` pattern still matches a `meta` line, so a teammate's first prompt (wrapped in `<teammate-message`) can open a run; anchor on the wrapper or leave the pattern unanchored.
8. A sub-agent's type comes from its own record first, then the parent's launching call, then the file name, and the ruler counts each source in `tipo_de_ajudante_por_fonte`.
9. A tool result is a hook denial, an exit code, an echoed `EXIT=N` (only when the command has `EXIT=$?`), an interruption, ok or an error, in that order; a hook denial is never a failed step.
10. Commands are matched whole, never truncated.
11. Content is counted, never copied: no message text, command, path, result text or sub-agent task text leaves the reader.

Design choices behind the rules:

- The reply lookup and `--prazo-uso-h` count from the run's opening, not its end, because a chat-channel reply is a `meta` line that stays inside the run; the action lookup starts at the run's end.
- Reply and action are looked for only in the run's own session, and the lookup stops at the next run in the same file; a sub-agent run nested in a main-file run therefore never cuts the main run's lookup short.
- A typed slash command also ends a run.
- Medians are taken over one number per run, `contexto + escritos`.

Several of these rules re-implement rules from Anthropic's `session-report` plugin (`skills/session-report/analyze-sessions.mjs`, Apache-2.0); see the package's NOTICE.

## The growth rule

When a review needs a transcript number the reader cannot give, the report writes it as one line, `not measured: the reader lacks <question>` (the question in plain words), and the skill never writes a script to get it.
That line becomes the next one-decision change: one new question in the reader, planned alone, with its before number (the review without it) and its after number (the same review's measure with it).
It is kept only if the numbers moved and the old answers did not change (the existing suite stays green); otherwise it is put back.

## Known limits

- Delivery outside Claude Code (a chat channel, a server's journal, a CRM's history) is not in the transcripts; a review writes it as "not verifiable here" with the command the user would run.
- A hook that lets a call pass leaves no line, so only its denials are counted.
- People's effort is not recorded anywhere the reader can see.
- Questions the reader does not answer yet include sub-agent cost across a whole window, the cost of text a hook injects, command outcomes outside a run, tool calls by name and the wake cost of every session; each waits for a real review that needs it (the growth rule).
- Tested on macOS and Linux; Windows is expected to work (call `python` instead of `python3`) but is not tested.
- The transcript format is Claude Code's own and undocumented; `formato_mudou` is how the reader says a change reached it.

## Tests

From a clean clone of the package, at its root:

```
uv run --with pytest python -B -m pytest -q tests
```

Without uv: `python -m pip install pytest`, then `python -B -m pytest -q tests`.
The tests point every default folder at a temporary one, so they never read the real transcripts.

## Glossary

| Name | Meaning |
|---|---|
| `--pasta` | the transcripts folder to read |
| `--de` | the window's start ("from") |
| `--ate` | the window's end ("until") |
| `--sessao-propria` | the id of the session doing the measuring ("own session") |
| `--desde` | when the measuring session started ("since") |
| `--sem-sessao-propria` | no measuring session to leave out ("no own session") |
| `--exclui-sessao` | a whole session to leave out ("exclude session") |
| `--abre` | what opens a run ("opens") |
| `--fecha` | what closes a run ("closes") |
| `--resposta` | a message that counts as a reply ("reply") |
| `--acao` | a command that counts as acting on the result ("action") |
| `--prazo-uso-h` | hours after the opening to look for a reply or action ("use deadline, hours") |
| `--fuso` | the IANA time zone to read and show times in ("time zone") |
| `execucoes` | runs |
| `totais` | totals |
| `regua` | ruler: how the reading was done |
| `sessao` | session id |
| `agente` | sub-agent id (null in a main file) |
| `inicio` | run start, local time |
| `fim` | run end, local time |
| `sinais` | signals about the run |
| `estreito` | narrow cost |
| `largo` | wide cost |
| `acordar` | wake cost |
| `ajudantes` | sub-agents, per type |
| `comandos` | Bash commands of the run |
| `respondido` | replied to |
| `minutos_ate_resposta` | minutes from opening to reply |
| `agido` | acted on |
| `minutos_ate_acao` | minutes from run end to action |
| `uso_indefinido` | use not defined (no reply or action pattern given) |
| `entrada` | input tokens |
| `gravados` | cache-write tokens |
| `relidos` | cache-read tokens |
| `escritos` | output tokens |
| `contexto` | context tokens (input + cache write + cache read) |
| `chamadas` | model calls |
| `por_desfecho` | counts by outcome |
| `mais_de_uma_tentativa` | commands that failed, then succeeded |
| `n` | count |
| `numero` | the number the medians are over |
| `fonte` | source folder |
| `regra_da_pasta` | the rule that picked the folder |
| `fuso` | time zone used |
| `janela` | window |
| `medido_em` | measured at |
| `arquivos_lidos` | files read |
| `linhas_lidas` | lines read |
| `linhas_ilegiveis` | unreadable lines |
| `linhas_em_escrita` | lines still being written |
| `tipos_desconhecidos` | unknown record types |
| `excluidas` | excluded sessions |
| `duplicadas_por_uuid` | entries skipped as duplicates by uuid |
| `tipo_de_ajudante_por_fonte` | sub-agent types resolved, per source |
| `padroes` | the patterns given |
| `padroes_casados` | how many lines each pattern matched |
| `formato_mudou` | format changed: the one stop signal |
| `avisos` | warnings |
