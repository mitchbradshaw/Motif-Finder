# Research prompt 00 — can the app answer the six questions?

**This is the first prompt of stage 5.** Stages 1–4 built the tool. From here the tool is used. Nothing in
this prompt builds anything.

`docs/PIPELINE_PRD.md` ("How the research questions map onto the build") names six questions and, for each,
what it needs from the software. Your job is to find out, by **driving the running app**, which of the six
can be answered today, which are blocked, and on what.

## What you produce

One file: `docs/RESEARCH_READINESS.md`. A section per question, in this shape and no longer than it has to be:

- **The route** — the pages, in order, and the chain (block by block) that answers it. Name real blocks from
  the registry, not plausible ones.
- **What you ran** — the chain, the scope, the run id. Real data, not fixtures.
- **What came out** — the actual number or figure, quoted.
- **What stops it** — the first thing that makes the question unanswerable, with the file and line or the
  page state. One blocker is enough; you do not need to find them all.
- **What it would take** — a sentence. Not a design.

Then one table at the top: the six questions, ranked by how close each is to answerable.

## How to run it

- A **`--sandbox`** bridge, which copies the real database and redirects every write
  (`webui/run_server.py --sandbox`, read `webui/server/runtime.py`'s docstring first). The real
  accumulating mode is `--project` and it is **the researcher's to run, never yours** — runs you make in it
  cannot be undone.
- Real data through the sandbox copy is the point: a route that works on fixtures and not on the corpus has
  not been tested. The held-out recording is refused on every route; leave it that way.
- Drive the browser. A page that constructs has not necessarily painted — that is why `webui/smoke.py`
  exists — and this whole stage's method has been to measure rather than to read the code and infer.

## Rules

1. **Fix nothing.** If a page is wrong, record it with the evidence and move on. A readiness pass that turns
   into a fixup tells you about one bug instead of about six questions.
2. **Report an absence as an absence.** "The Training pages are fixture-backed and wear a `demo data` chip"
   is a finding. Do not work around it and do not present a fixture number as a result.
3. **Quote, do not paraphrase, any number you report**, and say which store it came from.
4. **Stop and report** if a question needs a capability that is not there at all. That is the answer to the
   question you were asked.

## What is already known, so you do not re-derive it

Read these before you start; each bears on at least one question.

- `docs/prompts/fixup/README.md` — the state of every page, and "What is left after wave 3". **Jobs, Models
  and Training are still fixture pages.** Questions 1 and 6 lean on them.
- `docs/prompts/fixup/QUESTIONS.md` **Q26** is open and is a research decision, not an engineering one:
  41 % of the seed store and 34 % of the Library have **no recovery time and no FWHM** under the current
  definition, all of it sharkfin morphology. Any question whose answer is a distribution over those measures
  inherits it.
- `docs/prompts/fixup/future/R-interrogation-null.md` — **there is no null anywhere in the app.** Both
  fabricated ones were deleted on 2026-10-02 and the real one is not built. So no page can tell you whether
  a number beats chance, and no section of your report may imply one does.
- **Fan-out** does not exist in a chain (`Q-B-CHAIN`, open; the PRD forbids it inside a chain and puts
  comparison in a Compare action over two runs). Question 4 asks for band decomposition across bands.
  Establish early whether its route exists at all.
- `docs/prompts/fixup/reports/` — ten reports from the fixup wave. Each one's "Items left" is a list of
  things that are still not true. `H`'s and `K`'s are the newest.
- `docs/BLOCK_INTEGRATION.md` §2 — the drawing standard, so you can tell a view that is honest about an
  absence from a view that is missing something.

## Order

Do the cheapest first: the question whose route is most nearly complete, so there is a worked example in the
file before you hit the blocked ones. You may reorder freely and say why.

## If you need a decision

Put it in `docs/prompts/research/QUESTIONS.md` under `Round 1 — readiness` and stop there rather than
guessing. A research decision is the researcher's.
