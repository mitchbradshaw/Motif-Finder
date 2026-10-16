# Writing the manual

How to write any part of `docs/manual/`. For building it, see `README.md`.

## Who reads what

- **Part I** (chapters 01–15) is for someone new to the field: a student, an examiner, a
  collaborator, who wants to use the site. Plain words, no maths. Explain each technical idea
  the first time it appears, in a `plainterms` box, with an everyday analogy where one helps.
- **Part II and the appendices** are for a researcher or an agent who wants to know exactly
  what the code does, to check it or build on it. Be precise and cite the code.

The same idea often appears in both: plainly in the block card or page section, exactly in
the appendix entry or Part II, each linking to the other.

## Voice

- British spelling (analyse, colour, behaviour, normalise), as the app uses.
- Second person, present tense, active voice: "You pick a span, then press \ui{Run chain}."
- Short sentences. One idea per sentence. No filler, no marketing words ("powerful",
  "seamless", "simply").
- Name every control exactly as the app shows it, with `\ui{...}`. Name pages as the
  navigation does: Explore, Analyse, Discovery, Models, Review, Library, Jobs, Settings.
- Don't retype the generated settings table in prose. Explain the two or three settings that
  matter, in words.

## Accuracy: the rules that matter most

1. **Read the code before you write about it.** For a block: its adapter in `Adapters/`, the
   `Working/` function it wraps, and its tests. For a page: its components in
   `webui/client/src/<workspace>/`, the calls it makes through `webui/client/src/api.ts`,
   and the bridge endpoints in `webui/server/`. Cite code as `\code{path}` plus the function
   name; line numbers drift, names don't.
2. **Never guess.** If you can't confirm something from the code or a source in the repo,
   leave it out or wrap it in `\unverified{...}`. A `\towrite{...}` placeholder is better than
   a confident wrong sentence. A wrong manual is worse than an unfinished one.
3. **When the code disagrees with its docstring, a comment, its registry description or a
   doc, describe what the code does,** and report the disagreement (file and line) in your
   final message. These are often bugs.
4. **Validation means evidence that exists**: a test that checks the behaviour, an evidence
   script under `scripts/`, a document with results. Say plainly when a test only checks the
   plumbing (that the output has the right shape) rather than the answer. If there is none,
   write "No test in the repository checks …".
5. **Units and missing values.** Say what a block assumes. A block is unit-aware only if its
   `_run` (or `derive`) takes a `units` argument (the generated "Behaviour" line then says
   so); otherwise it works in the recording's stored unit, and any threshold in its settings
   means different things on volts and millivolts. Trace what happens to NaNs.
6. **Page status.** Mark a page `live` only when you have traced its data to the bridge
   (`api.ts` → `webui/server/`), `preview` when it reads `webui/client/src/fixtures/`, and
   `unchecked` when you could not tell. Say which parts are preview if a page is mixed.

## What you may touch

- **Only the files you were assigned.** Never edit `generated/` (it is rewritten by
  `scripts/manual_tables.py`), `ubmanual.sty`, `main.tex`, `bib/references.bib`, or another
  writer's files. If you need a new macro or a fix outside your files, say so in your report.
- **Read anything; run almost nothing.** Don't run pytest, the bridge, the smoke walk, or any
  adapter on data; don't import the adapters; don't install anything; don't commit; never
  touch `DATA/`. The one command you run is the slice check below.
- **Searching:** the repository is large (`node_modules`, `DATA`). Scope every Grep and Glob to
  a folder (`Adapters/`, `Working/`, `webui/client/src/`, `webui/server/`, `docs/`, `tests/`,
  `scripts/`). A search from the repository root times out.

## Check your work

From the repository root:

    "/c/ProgramData/anaconda3/python.exe" scripts/manual_check.py blocks <registry names...> --outdir docs/manual/build/check-<your-id>
    "/c/ProgramData/anaconda3/python.exe" scripts/manual_check.py chapter chapters/04-explore.tex --outdir docs/manual/build/check-<your-id>

Fix every error it prints. References to other parts of the book show as unresolved in a
slice build; that is fine. Citations show as "?" (BibTeX runs only in the full build).

## Bibliography

Put entries in `docs/manual/bib/<your-id>.bib` (create it); the orchestrator merges them into
`bib/references.bib`. Key: first author's surname, year, first significant title word, lower
case ASCII: `adamatzky2023multiscalar`. Check `bib/references.bib` first, and take details
from `docs/research/analysis-blocks-primary-sources.md`, which lists most sources with DOIs.
Cite with `\citet{key}` ("Adamatzky et al. (2023)") or `\citep{key}` ("(Adamatzky et al., 2023)").

## Templates

### A block: two hand-written files

`blocks/<stage>/<short>/card.tex`, for the blocks chapter of Part I. Plain language, half a
page at most. Five fields, each a `\cardfield{...}` followed by its text:

- **What it does**: one plain sentence.
- **When to use it.**
- **What goes in, what comes out**: in everyday words.
- **Settings that matter**: the two or three worth knowing.
- **Watch out for.**

`blocks/<stage>/<short>/entry.tex`, for Appendix A. Each field is an `\entryfield{...}`:

- **Algorithm**: what the code computes, step by step, as maths or `algorithmic`
  pseudocode, naming the functions.
- **Assumptions**: units, sampling rate, missing values (NaN), span length, signal shape.
- **Outputs**: the type, what goes in `meta`, where results are stored.
- **Cost**: time and memory as the span grows; limits such as a maximum span; whether it
  is meant for the cluster.
- **Failure modes.**
- **Validation.**
- **References.**
- **Tests.**

Above your text the entry already shows, from the registry: registry name, display name,
category, input and output types, code path, side inputs, behaviour flags, the registry's own
description, and every setting with its default and allowed values. The card already shows
its title, category tag, input and output types and the link to the entry.

**Worked example: `blocks/detection/spike_v1/`** (card and entry). Match its depth.

### A page of the app

    \pagesection{<id from webui/client/src/shell/pages.ts>}{Title}{one-line purpose}{live|preview|unchecked}

then a sentence or two on what the page is for, and:

- `\pagefield{When you'd come here}`
- a `\screenshot`
- `\pagefield{Doing things here}`: numbered steps for each common task, naming each control
  with `\ui{...}`. A task worth its own heading can be a `\subsection`.
- `\pagefield{Where it leads}`: which page you go to next, linked with `\apppage{id}`.
- where useful, a `watchout` box and an `underthehood` box (the client component, the bridge
  endpoint, the core function).

Keep the `\pagesection` ids exactly as the skeleton has them: they are the page ids in
`pages.ts`, and other chapters link to them.

**Screenshots:** `\screenshot{pages/<group>/<page-id>--<state>}{caption}` shows
`webui/screenshots/pages/<group>/<page-id>--<state>.png` (written by the smoke walk; the
names are stable). Prefer states with real data. The caption says what the reader should
notice, not "Screenshot of…".

## Commands

| Command | Use |
|---|---|
| `\towrite{note}` | A visible placeholder; counted on the title page |
| `\unverified{claim}` | A claim you could not check; shown in orange and counted |
| `\begin{plainterms}[Title] … \end{plainterms}` | Everyday explanation of an idea |
| `\begin{watchout}[Title] … \end{watchout}` | A pitfall |
| `\begin{underthehood}[Title] … \end{underthehood}` | Code pointers for researchers and agents |
| `\ui{Run chain}` | A control's label, as the app shows it |
| `\code{Working/units.py}` | A path or identifier; no escaping needed, breaks across lines |
| `\blockref{detection.spike_v1}` | A block's name, linked to its card |
| `\blockentry{detection.spike_v1}` | "Appendix A.x.y", linked to the block's entry |
| `\apppage{explore.signal}` | A page's title and section number, linked |
| `\term{span}{spans}` | Text linked to a glossary entry (keys: see `chapters/15-glossary.tex`) |
| `\catbadge{detect}` | A category's coloured tag |
| `\screenshot[width]{path}{caption}` | A screenshot from `webui/screenshots/` |
| `\faq{Question?}` | A question in the questions-and-answers chapter |
| `\pagesection`, `\pagefield`, `\pageanchor{id}` | Page sections (above) |
| `\cardfield`, `\entryfield` | Block fields (above) |
| `\ubnumblocks` | The number of blocks, from the registry |

Labels: chapters are `ch:<name>` (see each chapter's first line), appendices `app:blocks`,
`app:nulls`, `app:data`, `app:references`; a page section `page:<id>`; a block's card
`block:<registry name>` and entry `app:block:<registry name>`; a category `cat:<category>`.
Your own section labels: `sec:<chapter>-<slug>`. Link with `\cref{...}`.

Glossary keys: link only to keys that exist in `chapters/15-glossary.tex`; list any new term
you needed in your report rather than adding a key to someone else's file.

Avoid non-ASCII characters inside `lstlisting` code blocks (listings cannot set them).

Never put `\code{...}` inside a heading, a caption (including `\screenshot`'s), a `\faq`
question or any other moving argument: it breaks the table of contents. Use `\texttt{...}`
there, escaping underscores as `\_`.

## Report back

Your final message, in this order:

1. Files written.
2. Anything left `\towrite`, and why.
3. Claims marked `\unverified`.
4. Questions for the researcher. Each opens with a plain-language explanation of what is at
   stake, as if to someone new to the field, then the options, then your recommendation
   (a standing rule of this project; see `CLAUDE.md`).
5. Discrepancies between the code and its docstrings, comments or docs: possible bugs, with
   file and line.
