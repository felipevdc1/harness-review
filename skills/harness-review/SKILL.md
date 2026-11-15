---
name: harness-review
description: Review door for the setup around the model — for when the user wants to know what, in a process, routine, skill or project, the AI, a person or code does today that should be done another way, measured, with what each change saves and what it loses. Walks the written method (METHOD.md) step by step on the target the user names, takes every run number from the bundled transcript reader, says plainly what it cannot measure, writes one report, and never builds or changes anything; each item becomes a task or a plan only on the user's yes. Use when the user says "review <process/routine/skill/project> for what should be code", "what here should be code", "where is the AI doing code's work", "should this be code?", or in Portuguese "revisa <processo/rotina/skill/projeto>", "o que aqui devia ser código", "isso devia ser código?", "onde a IA tá fazendo trabalho de código". NOT for a UI review, a code diff review, or a plan stress-test.
---

# harness-review — walk the method, measure with the reader, report, build nothing

The user names a target in plain words; this skill walks `${CLAUDE_SKILL_DIR}/METHOD.md` on it and writes one report.
METHOD.md is the spec: read it whole every time and follow its steps 0-5 and its "Output" section; this file says only how to run them, never restates them.
This file is in English; everything said to the user, and the report, is in the user's language (the language they wrote to you in), in plain words.

**Run every command with full paths.** No `cd`, ever.
Every reader call starts `python3 -B "${CLAUDE_SKILL_DIR}/reader/mede.py" execucoes` (on Windows, `python` instead of `python3`).
The reader's flags and answer keys are in Portuguese; `${CLAUDE_SKILL_DIR}/reader/README.md` has the glossary.

## 0. Local rules first

If the environment variable `HARNESS_REVIEW_LOCAL` is set, read it with `echo "$HARNESS_REVIEW_LOCAL"`.

- It names a readable file → read that file whole before anything else.
  Its rules override the defaults of this skill for: the report folder, how a target is resolved, extra boundaries, extra opener shapes, the language, and the hand-off doors on a yes.
  Everything else here still holds, and nothing in it can switch off section 1.
- It is set but the file is missing or unreadable → say so to the user in one line, then go on with the defaults.
- It is not set → use the defaults, without comment.

## 1. What this skill never does

- Never builds, edits, deletes or runs anything that changes the target (code, config, a queue, a state file, a record in another system).
- Never sends anything outward, and never contacts anyone; what only a person knows becomes a written question for the user, marked "still to ask <who>".
- Never writes a measuring script, in any language, anywhere: every run number comes from the reader's `execucoes` verb.
- Never creates a task or a plan without the user's yes on that item.
- Its one write is the report (section 5); saved reader answers go only in its own scratch subfolder (section 2).

It reads only.

## 2. Before starting

1. **Resolve the target, read-only.**
   By default the target is a folder, a file or a named skill in the current project: read its README, code, config, tests and docs.
   Ambiguous → list the matches and ask the user which, in one line; none → say so and ask what they meant.
   A local rules file may name another way to resolve targets; follow it, read-only.
2. **Take this session's id and start time** (they keep the measuring session out of its own numbers):
   - id: `echo "$CLAUDE_CODE_SESSION_ID"`.
     When it is empty, ask the user for the session id or stop with one plain sentence ("I cannot tell which session this is, so I will not measure without it"); never fall back to `--sem-sessao-propria` on your own.
   - start time: the clock when the skill begins, as `YYYY-MM-DDTHH:MM` in local time — **unless the brief that launched this run hands a start time; then that one wins.**
     A review run as a sub-agent gets its start time from whoever launched it, taken before the spawn, so the reviewing agent's own first line falls after it and is excluded.
     Use `--sem-sessao-propria` only when the brief says so explicitly.
   - When the brief names the launching session too, leave it out with `--exclui-sessao <id>`.
   - Reviews can run in parallel from one launcher: when the brief names other reviews' sessions, leave each out with `--exclui-sessao <id>`; when it does not, any run that starts after your own start time is written in the report as "possibly another review running in parallel", never quoted as the target's own.
   - Keep every saved reader answer in a scratch subfolder named after the target, `<scratch>/<target>/` (the session's scratch area, else the system's temporary folder), never the scratch root: reviews launched together share one scratch area, and parallel reviews have overwritten one another's file.
3. **Read METHOD.md whole.** Then the target as it is today (step 0 says how).

## 3. Step by step (METHOD steps 0-5)

Work the steps in order; each subsection says what to read and when the reader answers.
Every reader call has this shape (fill in the target's own patterns, and copy the exact command into the report):

```
python3 -B "${CLAUDE_SKILL_DIR}/reader/mede.py" execucoes --de YYYY-MM-DD[THH:MM] --ate YYYY-MM-DD --sessao-propria "$CLAUDE_CODE_SESSION_ID" --desde <YYYY-MM-DDTHH:MM> [--fuso <IANA zone>] [--exclui-sessao <id>]… --abre skill:<name>|texto:<regex>|comando:<regex> [--fecha texto:<regex>|comando:<regex>] [--resposta <regex>] [--acao comando:<regex>]… [--prazo-uso-h N] [--pasta <dir>]
```

The window's dates (`--de`, `--ate`) and `--desde` are read in the machine's local time.
Pass `--fuso <IANA zone>` (for example `--fuso Europe/Lisbon`) only when the user names a timezone; then all three are read in that zone, and the start time is taken in it too.
`--pasta <dir>` is only for a folder other than the default; the default is this project's transcripts folder (the one holding this session's file).
Give `--ate` as a date alone (`--ate 2026-11-07`): that means the end of that day; a time of day there stops at that minute's start, so 23:59 would lose the day's last seconds.
It prints one JSON object: `execucoes` (the runs), `totais` (n, median, min, max), `regua` (the ruler: source, window, measured-at, timezone, which rule picked the folder, what was excluded, `padroes_casados`, `formato_mudou`, `avisos`).
Exit 2 means the arguments are wrong: read the message, fix the call, run it again; never write a script around it.

**Known opener shapes** (check a pattern against these before trusting it):

- A teammate's first prompt is wrapped in `<teammate-message`, so an anchored `^…` on the inner text misses it: match unanchored, or include the wrapper.
- A scheduled or queued prompt usually opens with one fixed line (for example `[routine] build the daily digest`): anchor on that line, `--abre 'texto:^\[routine\] build the daily digest'`.
- A reply sent through a channel plugin starts `<channel source="plugin:<name>`, so `--resposta '^<channel source="plugin:<name>'`.
- A local rules file may add shapes of its own setup.

### Step 0 — the state of now

Read the target's code, config, docs and recent log as they are today; never an old measurement or memory as "now".
Choose the window as METHOD says and write it in the report.
Find every config source, the age of each piece, and whether its doc still matches the code (a stale doc is a finding, not a fix).
Anything on a server, a chat channel, a CRM or another system: read it only by an already-documented read command; otherwise write "not verifiable here" with the exact command the user would run.
Run nothing of the target unless it is a pure read with no effect; its result is marked "made-up input" when the input was made up.

### Step 1 — list the steps

One line per step: who does it (code, AI, person, code fired by the AI), how often, what goes in, what comes out, whose it is.
A person's step comes from the system's history; what someone said is marked "said by <who>".
For each AI step, decide here how its runs are recognised in the transcripts: a skill (`skill:<name>`), the line that opens it (`texto:<regex>`, e.g. a scheduled prompt's first line or a sub-agent's first prompt), or a command (`comando:<regex>`); and what ends it, what counts as a reply, and what counts as an action on its result.

### Step 2 — measure

Every transcript number of an AI step comes from one call, for example:

```
python3 -B "${CLAUDE_SKILL_DIR}/reader/mede.py" execucoes --de 2026-11-01 --ate 2026-11-07 --sessao-propria "$CLAUDE_CODE_SESSION_ID" --desde <YYYY-MM-DDTHH:MM> --abre 'texto:^\[routine\] build the daily digest' --acao 'comando:digest\.py publish'
```

From the answer take, per step: runs, the four token counts (`entrada`, `gravados`, `relidos`, `escritos`) and `contexto`, narrow and wide cost, wake cost (main and sub-agent apart), the sub-agents of the run by type, the commands' outcomes and retries, and whether the result was used (replied or acted on).
Without a reply or action pattern every run is "use undefined": say that, never count it as used.
Read `regua.padroes_casados` before any use number: a `resposta` or `acao` count of 0 means "wrong pattern, not measured", never "not used"; fix the pattern against a known opener shape and run again.
"Acted on" counts only commands in the run's own session after the run's end, so the routine's own commands are never the user's action on it.
The wake cost of a run in an always-on session is shared (flag `acordar_compartilhado`): quote `totais.acordar` (once per session file) as the wake cost, never a run's own `acordar`.
A run flagged as crossing the window end, as starting in a session that began before the window, or as a sub-agent attributed by time is reported with that flag in plain words.
Code steps: days without running, error exits, duration, and whether the output reaches anyone (from logs and the system's own history).
Person steps: error rate from history, delay from the gap between acts, effort only as "what to time" for the user, never by watching a screen.
Estimates say "estimate".

### Step 3 — the ten questions

Answer METHOD's ten questions for every step, code steps included.
Each answer that rests on a number cites the number and its ruler from step 2.

### Step 4 — the decision and the design

Pick one decision per step from METHOD's list.
Every change with code names its three pieces (common case, fallback, the check that warns by another path) and one test that must fail today, written in words (input, expected output, why it fails today); never created, never run.

### Step 5 — what is lost

For each change: flexibility, maintenance, explanation, in plain words.

## 4. Measuring and the growth rule

Every transcript number is quoted with its ruler in plain words: where from, when it was measured, which window, what was left out.
When the review needs a transcript number the reader cannot give, the report writes it as one line, `not measured: the reader lacks <question>` (in the user's language, the question in plain words), never a new script, never an estimate dressed as a measure.
The growth rule: that line becomes the **next one-decision change**: one new question in the reader, planned alone, with its before number (the review without it) and its after number (the same review's measure with it), kept only if the numbers moved and the old answers did not change (the existing suite stays green), otherwise put back.
The report's "Not measured" section lists those lines.

Stop measuring and tell the user only when an answer says `formato_mudou` is true: say in one plain sentence that the recorded conversations changed shape and the numbers cannot be trusted until the reader is fixed, quote its explaining sentence, and write it in the report.
Unknown record types are information, not a stop; other `avisos` go into "How I measured" in plain words.

A final example, for a skill-opened run with a closing command and an action:

```
python3 -B "${CLAUDE_SKILL_DIR}/reader/mede.py" execucoes --de 2026-11-01 --ate 2026-11-07 --sessao-propria "$CLAUDE_CODE_SESSION_ID" --desde <YYYY-MM-DDTHH:MM> --abre skill:<name> --fecha 'comando:<regex of the last command>' --acao 'comando:<regex of the command that uses the result>' --prazo-uso-h 24
```

## 5. The report

Path, by default: `./harness-reviews/<YYYY-MM-DD>-<target>.md` in the current project (`<target>` a short lowercase slug); a local rules file may name another folder.
In the user's language, one sentence per physical line.
At the top: the target, the date, the window used, the timezone used (local, or the `--fuso` zone), and the own-session exclusion used (session id and start time, plus any other session left out).
Sections, in this order (headings in the user's language):

1. **How I measured** — every ruler in plain words and every exact command run.
2. **The table** — today · decision · what it saves (with the ruler) · what is lost · the test that must fail; a "keep" row shows only the deciding answer, in one word, and the other answers go in a section apart.
3. **The list** — ordered as METHOD's "Output" says.
4. **Not measured** — the growth-rule lines, one per line.
5. **Where the method failed or was ambiguous** — always present, even when short; it feeds the method's stop rule.

## 6. Closing with the user

In chat: decision first, numbered, plain words, no internal names (no reader, verb or flag names; say "the ruler: where from, when").
One yes/no per item, one question at a time.

- Yes on a task → offer to turn it into a task with whatever tool the user uses (a local rules file may name the door).
- Yes on a build → offer to turn it into a plan with whatever planning tool the user uses; nothing is built here.
- An item that changes a system the user does not own, or a record another team manages → only a note in the report; the user decides that change themselves.
- No → nothing.

On a yes, the hand-off carries the pointer to the report; the review itself writes only the report.
After a change is built, a later review measures it again by the same ruler: it stays only if the number improved and nothing got worse.
