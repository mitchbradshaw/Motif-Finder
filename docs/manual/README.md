# docs/manual: the Underground Brains manual

The user manual for the web UI, in LaTeX. Part I teaches anyone to use the site; Part II and
the appendices say exactly what the code does, for researchers and agents building on it.
How to write it: `AUTHORING.md`.

## Build

    cd docs/manual
    latexmk                # builds build/main.pdf (pdflatex + BibTeX; settings in latexmkrc)

**Live preview beside your editor:** open this folder in VS Code (`code docs/manual`), open
`main.tex`, and press Ctrl+Alt+V. LaTeX Workshop rebuilds whenever any source file changes,
including edits made outside VS Code by an agent, and refreshes the PDF tab. Ctrl+click in the
PDF jumps to the source line. Workspace settings: `.vscode/settings.json`.

## Layout

| Path | What | Who writes it |
|---|---|---|
| `main.tex` | The book: parts, chapter order, bibliography | by hand |
| `ubmanual.sty` | House style and every macro (listed in `AUTHORING.md`) | by hand |
| `chapters/` | Part I (00–15) and Part II (16–17) | by hand |
| `appendices/` | A: block reference, B: nulls and statistics, C: data and units | by hand (A's body is generated) |
| `blocks/<stage>/<short>/card.tex` | A block's plain-language card (Part I) | by hand, from a generated stub |
| `blocks/<stage>/<short>/entry.tex` | A block's full appendix entry | by hand, from a generated stub |
| `generated/` | Block metadata, settings tables, catalogue order, version stamp | `scripts/manual_tables.py` only |
| `bib/references.bib` | The bibliography | by hand |
| `OPEN_QUESTIONS.md` | Questions for the researcher and possible bugs found while writing the manual | by hand |
| `build/` | Output; gitignored | latexmk |

## When the code changes

- **A block was added, removed or changed its settings:** run
  `python scripts/manual_tables.py` (conda python, from the repo root). It rewrites
  `generated/` and creates stubs for any new block; it never overwrites hand-written text.
  Then write the new block's card and entry.
- **Is the manual in step with the registry?** `python scripts/manual_tables.py --check`
  writes nothing and exits 1 if a generated file is stale, a block lacks its card or entry,
  or a hand-written folder names a block that no longer exists.
- **Check one slice without building the book:** `python scripts/manual_check.py blocks
  <registry names...> --outdir <folder>` or `... chapter chapters/04-explore.tex --outdir
  <folder>`.
- **A page was added to the app** (`webui/client/src/shell/pages.ts`): give it a
  `\pagesection` with the same id in its workspace's chapter.

## Toolchain

TinyTeX (TeX Live 2025) with tcolorbox, enumitem, cleveref, siunitx, listings, caption,
titlesec, fancyhdr, algorithms, algorithmicx, needspace, mathtools, parskip and xurl added
(2026-10-15, from the frozen 2025 archive, since CTAN now serves 2026):

    tlmgr --repository https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2025/tlnet-final install <package>

tcolorbox 6.9 expects a newer LaTeX kernel than this TinyTeX's; `ubmanual.sty` supplies the
two PDF-tagging commands it calls as no-ops, which is harmless because tagging is off. The
draft markers (`\towrite`, `\unverified`) are counted on the title page.
