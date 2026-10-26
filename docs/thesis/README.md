# Thesis: MycoWave

The METR4911 thesis. It is due **Mon 9 Nov 2026, 3 pm**. The structure and content decisions were settled in the
planning (grilling) session on 2026-10-26.

## Build

From this folder:

```bash
latexmk
```

The output is `build/main.pdf`. TinyTeX lives at `C:\tools\TinyTeX\bin\windows`. Three packages were added on
2026-10-26 from the TeX Live 2025 archive: multirow, makecell and ieeetran.

## Layout

| Path | Contents |
|---|---|
| `main.tex`, `preamble.tex` | The document, plus packages and macros. Spacing is 1.5 with 2.5 cm margins. |
| `frontmatter/` | Title page, letter, declaration, AI-use statement, acknowledgements, abstract. |
| `chapters/01–11` | One file per chapter (structure agreed in Round 2, Q2). |
| `appendices/A–G` | Repository, blocks, vocabulary, numbers ledger, claims ledger, exam record, decision log. Keep these to 8–10 pages. |
| `tikz/` | Four diagrams: the RQ mapping, the architecture, the types and the adjudication loop. |
| `figures/` | Copied figures: the plan's images, poster panels and charts, demo screenshots, drop-motif figures, run reports. |
| `data/` | Analysis outputs written by `scripts/thesis/` and `Pipelines/fhn/`. |
| `numbers_ledger.md` | Every quoted number, with its source and status. Appendix D is generated from it. |
| `bib/thesis.bib` | BibTeX entries. Those marked `% VERIFY` were added on 26 Oct; check each against the paper. |

## Conventions

- **Purple text is a content note for the author.** It uses the plan's `instructions` environment and states what
  each paragraph must say, with numbers and source paths. Delete every note before submission.
  `\src{path}` prints a path inside a note.
- `\tool{}` prints the software's name, MycoWave.
- Copied figures are snapshots. Re-shoot the UI screenshots on 8765 after the freeze (Tue 3 Nov), and regenerate data
  figures with the scripts in `scripts/thesis/` rather than editing the images.
- Prose carried over from the August plan has been corrected where the facts changed. Prose for new sections is the
  author's to write.
