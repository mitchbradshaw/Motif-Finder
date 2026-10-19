"""Reports: the figures and tables behind a result (docs/prompts/changes/reports.md).

A report is what a researcher pastes into a thesis chapter or shows a supervisor:
PNG figures drawn here with matplotlib (the one drawing library the core keeps,
Agg canvas, no pyplot), GitHub-flavoured Markdown tables, and an HTML wrapper
that embeds the same PNGs. The app shows that HTML; the browser's print saves it
as PDF; a snapshot writes the three side by side. Never a screenshot of a page.

* `detection_run` — one Discovery run against the human reference;
* `formatting`    — the Discovery page's own way of printing a number;
* `figures`       — the matplotlib figures, each returned as PNG bytes;
* `render`        — Markdown, HTML, and the snapshot directory;
* `store`         — the `reports` table: a snapshot's PATH, never its bytes;
* `provenance`    — the code commit, the date and the account at render time.

UI-free (CLAUDE.md rule 1): nothing here imports a server or browser library.
"""
