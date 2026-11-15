# daily-digest — a toy routine to review

A small, made-up routine for trying harness-review on something that is not your own work.

## What it does

Every morning a scheduled prompt opens a session with:

```
[routine] build the daily digest
```

The AI then:

1. reads `inbox.json` (a list of items, each with a `priority` field: 1 is the most urgent);
2. sorts the items by `priority`, 1 first;
3. writes `digest.md`.

Later the user reads the digest and, when it is worth keeping, runs:

```
python3 digest.py publish
```

which copies `digest.md` into `published/digest-<date>.md`.
That command is the user's act: it is how a review tells a digest that was used from one that was ignored.

## Files

- `inbox.json` — a sample inbox.
- `digest.py` — the user's `publish` command, nothing else.
- `../transcripts/-example/` — seven synthetic mornings (2026-11-01 to 2026-11-07, UTC) of this routine in the shape Claude Code records sessions: seven main files and one sub-agent file (on 11-03 the routine hands two long items to a helper).
  The user publishes on 11-02, 11-04 and 11-06, answers without publishing on 11-05, and never comes back on the other three days.
  Every usage number is made up.

The transcripts are written by `../make_transcripts.py`, which gives the same bytes on every run:

```
python3 -B examples/make_transcripts.py           # rewrite them
python3 -B examples/make_transcripts.py --check   # exit 0 when the committed files match
```

## Trying the review on it

From the package folder, measure the seven runs and how many were acted on:

```
python3 -B skills/harness-review/reader/mede.py execucoes \
  --pasta examples/transcripts/-example --de 2026-11-01 --ate 2026-11-07 \
  --sem-sessao-propria --abre 'texto:^\[routine\] build the daily digest' \
  --acao 'comando:digest\.py publish' --fuso UTC
```

`totais.n` is 7 and three runs come back with `agido: true`.

Then ask the skill to review `examples/daily-digest` with those transcripts.
Step 2, the sort, is the part to watch: a fixed field and a fixed order is a decision code can make every time, so a good review flags it as a code candidate.
