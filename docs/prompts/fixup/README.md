# Stage 4 — the Fixup Wave

Prompts for the round after wiring (`docs/prompts/wiring/`, prompts 00–05, all run). Wiring made the
pages read and write real data. This stage fixes what the live data then showed to be wrong, broken or
missing — from the wiring reports' own "Left" / "What is still not true" lists, from the critics'
unfixed findings, and from the user's and the supervisor's use of the running app.

**These files are skeletons.** They carry the *symptoms* — grouped by page, each traced to its evidence
(a report section, a source line, or a screenshot) — and nothing else. The prompt body, the file list,
the test-first work plan and the gate are written only after the questions in
`QUESTIONS.md` are answered, because most of the symptoms below are one design decision away from
being either a bug or a spec change.

| File | Workspace / pages |
|---|---|
| `A-no-decision-fixes.md` | **written and ready to run** — the seventeen defects across six workspaces that have a known cause, a known line and exactly one defensible fix. Carries an explicit not-in-scope table so it cannot widen into the decisions still open |
| `00-cross-cutting.md` | the shell, the `demo` chip, shared chart primitives, naming, workflow |
| `01-explore.md` | Corpus, Signal, Cross-channel, Span edit |
| `02-analyse-chain.md` | Chain, Block, Algorithm glyphs |
| `03-analyse-interrogation.md` | Interrogation, Slope, Aggregate |
| `04-analyse-training.md` | Training chain, blocks 01–05 |
| `05-discovery.md` | Runs, Seed search, Compare, Compare every stage |
| `06-models.md` | Launch, Results, Compare, Registry |
| `07-review.md` | Queue (inspector), Cluster |
| `08-library.md` | Recurrence, Atlas, Family, Edit grouping, Import, Window sets, Templates |
| `09-jobs.md` | All jobs, Paused run, Upload and continue, Cluster job |
| `10-settings.md` | the sixteen settings pages |

`QUESTIONS.md` is the live list of what must be decided before a prompt can be written, with the
answers recorded beside each question as they are given.

Reports go in `reports/`, cross-agent requests in `requests/`, same convention as the wiring stage.
