# Method: what the AI, a person or code does that should be done another way

Version 1.0
It serves a project, a part of one, or a process, whether it runs on your machine or inside an organisation.
It looks both ways: an AI or a person doing what should be code, and code doing what needs judgment.
The review builds nothing; each item becomes a task or a plan only on the user's yes.
The review's only write is the report, in the reports folder; nothing else, in the target or outside it.
Marked phrases below are given in English; the report writes them in the user's language.

## Step 0: the state of now

Read the target as it is today (code, configuration, recent log), never through an old measurement or from memory.
Default window: 7 days, stated in the report.
A code or configuration change inside the window does not shorten it: it splits the measure into before and after, and only when the change touches the step being measured (a change that does not touch it is stated and splits nothing).
For a process that has run for less than the window, the window is the time it has lived.
For a process that runs less often than the window (an invoice check that runs once a month), the window grows until it covers the last two whole runs, and the report says so.
One side of a split window with fewer than 3 runs (a chosen limit, with no measure behind it) shows its runs one by one, with no average and no conclusion, and the step stays "keep and measure" until it has 3.
Two rulers of the system with different starts: the one that starts later is used, and the difference is a finding.
With no creation date on disk, the age is "age not verifiable"; on a system that keeps only the last write, say so.
Find every configuration source of the target (project, machine, plugins), not only the first one.
Note the age of each piece and of the pieces it depends on; a piece that changed or left inside the window splits the measure into before and after.
Check whether the target's document still matches the code; a stale document is a finding, not a fix.
A process paused or cut by its owner: measure the last period it ran, and the question becomes what is left to clean up (the review lists what to clean and its size; it deletes nothing).
In a process run by people, the document says what they should do; what they actually do comes from the system's history, marked "said by <who>" when it comes from someone.
The review never contacts anyone: what only a person knows becomes a written question for the user to ask, marked "still to ask <who>".
For a process that does not run yet, "today" is its newest plan.
Run something of the target only if it is a read with no effect: a pure function with made-up input may run, and its result is marked "made-up input".
Nothing that writes, sends, marks as read, claims a day or changes a state runs; when in doubt, "not verifiable here" with the command.
A test suite of the target runs only when its README or the tests themselves show that it writes only to a temporary folder, and with Python writing no cache (`-B`); otherwise "not verifiable here" with the command.
Reading another system through an already documented read command is allowed (for example a read-only ssh to a server); what needs a write, or has no read command, stays "not verifiable here", with the command the user would run.

## Step 1: list the steps

One line per step: who does it (code, AI, person, or code fired by the AI), how often, what goes in, what comes out, and whose it is (the user's, another organisation's, or a third-party engine you install).
A step is a decision or an action with its own input and output; a fixed sequence of commands the AI fires one by one is one step, and a strong candidate (a nightly notes routine that runs the same five commands in turn).
A chain of jobs, a correction loop and a hook on several events are one step each, with the count per part beside it.
The session that orchestrates is a step of its own, with its own cost, apart from what it calls.
No step skips the questions for already being code: code is questioned too (does it decide beyond the structure of its input? does it warn when it does not run?).
Small, identical pieces that never reach the model may share one line.

## Step 2: measure

The recorded conversations are measured by the reader, `reader/mede.py execucoes`; in a review it is used, never written or changed, and no measuring script is written, because every hand-written measure tried so far reinvented the reader and got it wrong at first.
A measure the reader does not give is written "not measured: the reader lacks <question>" and becomes an item of the list.
The pattern that recognises the step is the review's choice: also run a wider one, say how many runs each found and what the chosen one left out, and count by the one that loses no real run.
When no pattern separates the step from the work around it, use the closest one, state the number as a ceiling, and the separation becomes "not measured: the reader lacks <question>".
The system's own history (state files, logs, folder dates) is read with one-line read commands that only count (ls, wc, jq), each copied into the report.
Summing a field the system itself records (for example `jq -s` over a token log) is also allowed, and it is how an AI step that leaves no recorded conversation is measured.
That is not a measuring script; it does not apply to summing the reader's output: a total the reader does not give stays "not measured".
The traps of reading the conversations live in the reader's tests and README, not here.
The ruler of each number goes with it (from where, from when, which window), because a cost number ages.
Earlier measurements are only for comparison, never quoted as the number of now.

AI step: tokens written, re-read and stored, kept apart; narrow and wide cost when the turn mixes work.
Narrow cost: only the calls whose request is this step.
Wide cost: from the step's first call to the user's next real message (not marked `isMeta`); in an always-on session, the wide cost stops at the first request on another subject.
Wake cost can dominate in an AI setup, so it is measured in every review, split by kind: new session, always-on session, each sub-agent.
A text injected in the middle of a session is re-read on every later call; its cost is its size times the calls that come after.
A step's cost can live in another session (whoever launches a sub-agent, whoever is blocked by a hook); count it where it falls.
In a context that does several steps, divide by call and say so; two hooks on the same stop: divide equally, and list apart the stops with only one.
An act that leaves no trace when it succeeds (a stop hook or a prompt hook that lets a call pass) has no frequency in the history: say "not measurable from the history".
Person step: what weighs is usually the error; error rate from the history, delay from the gap between acts, effort only timed by the user with the person (the review says what to time), never by watching a screen.
Code step: days without running, error exits, duration, and whether what it produces reaches anyone.
Use of the result: first, is the output delivered to whoever acts on it? Then, was it used? A write is use; an item left waiting in a queue is not used.
Runs where "there was nothing to do today" are not a lack of use: they leave the count, and their number is shown beside it.
Teaching step: use is the word coming back in the user's own mouth.
Injected text: use is the model acting on it in some later call.
Block: use is the requested correction happening.
Memory: use is showing up in a search result that is read later.
With no history, every number is an estimate and says so; the first real measure becomes the baseline.
The measuring reads personal content: it counts, it does not copy.

## Step 3: the ten questions, for each step

1. Does it need to exist? A result used less than 1 time in 10 (per item when there are items, else per run) takes the cut to the user; this limit is chosen, with no measure behind it: below it the review takes the cut to the user, never cuts on its own.
2. Does it really need judgment? "It needs judgment" is often an excuse (Google SRE); but when the person's choice is the product itself (taste, approval), the judgment stays.
3. Does the input have structure? Code decides only as far as the structure goes, both ways: code guessing free text is as wrong as an AI reading a fixed field. If the structure existed at the source and was lost on the way, the fix is to stop losing it.
4. Is it already stable? With no history, the rule the user already gave holds; "it varies" stays with the person; a third party's rule, by that party's own change history.
5. How much does it pay? Measured gain (tokens, time, error avoided or risk avoided) against the cost to build and maintain. Build hours are an estimate in bands (under 1h, 1 day, more than 1 day), said as an estimate; never a pretend number.
6. Can it be undone, in the system and in the world? A payment passed on, a message sent and information discarded without a copy do not come back; state the size of the harm in three grades: undoes itself, undone with work, does not come back.
7. Whose is it? Another organisation's system, or a step the user reviews one by one, stays out of code without the user's yes; a third-party engine you install: changes go to its maintainers as a request, drafted, sent only on your yes; a step the user asked to keep stays.
8. What data leaves the machine, and to whom? An AI of another provider, a third party that is not an AI (a chat service, a group), or the same provider that already receives the session (nothing new). If question 8 calls for code and question 3 says the input is free text, question 3 wins and the change becomes "ask the owner" or "keep", with the data named.
9. If it does not run, does anyone notice? Silence must never look like "nothing new" (the hidden-failure problem Bainbridge describes); the check warns by a path that does not depend on what it watches.
10. When the code is wrong, which way? A classification (a support-ticket triage) errs both ways with different costs; say which side the check covers and whether the error stays visible (abstaining in plain sight beats being wrong in silence).

The ten are answered for every step.

## Step 4: the decision and the design

Possible decisions:

- cut;
- confirm the cut and clean up what is left (the review lists what to clean and its size; it deletes nothing);
- code;
- merge (a sequence of commands the AI fires becomes one command);
- preserve the structure (stop flattening data that already came structured);
- hybrid (code for the common case, AI or person for the rest; a code gate that decides whether the AI is called, such as a deploy hook that calls the model only on an unknown failure, is hybrid);
- give back to judgment (take out of the code what it guesses);
- check (the code checks the person or itself and warns);
- move (a lighter session, a smaller model, batching runs);
- ask the owner;
- bring the document up to date (a stale document becomes a documentation task, only on the user's yes; the review does not edit it);
- keep and measure;
- keep.

Every change that has code has three pieces: the code for the common case; the fallback for the rest; the check that stops and warns, by another path, when the code no longer fits (jidoka, stop and signal, as in the Toyota Production System; what the rule systems of the 1980s, such as XCON, lacked).
In "check" and in the gate, the fallback is whoever already does the step; the check watches whether the gate lets through what should have called the AI.
Code gathers and checks; choosing what is worth looking at stays with whoever has judgment (Dawes, after Meehl).
No money value comes from the AI: it fills fields, the arithmetic is code (an invoice check reads the amounts with the AI and adds them in code).
Every change has a test that must fail; for a cut, a habit, a request to the owner or a "keep and measure", it is a future measure with its limit written; for a "keep", the column says "—".
In the review, the test is written in words: input, expected output, why it fails today; it is never created or run.
Code that stores judgment is easy to delete if the AI gets better (Sutton); a money or contract rule stays code.

## Step 5: what is lost, in writing

For each change: the flexibility, the maintenance (in XCON about half the rules changed each year) and the explanation (the record keeps which rule matched).

## Output

A short table: what it is today, the decision, how much it pays (with its ruler), what is lost, the test that must fail.
In "keep" rows, the table shows only the answer that decided it, in one word, and the other answers go in a section apart.
Then the ordered list: first the risk items whose worst case cannot be undone (question 6), by severity; then the gain items, by what pays back fastest; third-party work by its gain, with the date as unknown; an item that depends on another decision comes right below it.
When nothing is measured, the order is an estimate and says so.
In a later review, after an approved change is built, measure again by the same ruler: it stays only if the number improved and nothing got worse.
When the target is a third-party engine you install, an update can change it, and the decision to keep it is not yours.

## Sources

- Toyota Production System (jidoka: stop and signal a problem): https://global.toyota/en/company/vision-and-philosophy/production-system/
- Google SRE, "Eliminating Toil": https://sre.google/sre-book/eliminating-toil/
- Google SRE, "Automation at Google": https://sre.google/sre-book/automation-at-google/
- Bainbridge, "Ironies of Automation" (1983): https://ckrybus.com/static/papers/Bainbridge_1983_Automatica.pdf
- Dawes, "The robust beauty of improper linear models in decision making" (1979), which reviews Meehl (1954): https://www.cmu.edu/dietrich/sds/docs/dawes/the-robust-beauty-of-improper-linear-models-in-decision-making.pdf
- XCON (expert system, rule maintenance): https://en.wikipedia.org/wiki/Xcon
- Sutton, "The Bitter Lesson" (2019): http://www.incompleteideas.net/IncIdeas/BitterLesson.html
