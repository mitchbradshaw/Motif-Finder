# ui-prototypes/ — frozen evidence archive

This directory is the record of the stack-selection prototypes for the UI rebuild (overnight
2026-09-14 → 15). It is kept as evidence and is not maintained.

- **[`REPORT.md`](REPORT.md) is the decision evidence** (scorecard §8); `DECISIONS.md` is the build log;
  `REAL_DATA_WRITES.md` inventories the files the prototype night wrote into the real `DATA/`. The
  benchmark script and its result, the checklist and the data-integrity snapshots stay beside them.
- **Prototype A (React + TypeScript + FastAPI) moved to [`../webui/`](../webui/)** on 2026-09-15 and is
  now the product web UI.
- **The prototype code trees and screenshots (`A-react-fastapi/`, `B-panel/`) were deleted on
  2026-09-21** together with the Panel tree; they are reachable at tag `archive/panel-ui`. Paths in
  `REPORT.md` §6 that point at `A-react-fastapi/screenshots/` resolve at that tag, not on `main`.
- The decision itself is recorded in [`../docs/adr/0001-web-ui-stack.md`](../docs/adr/0001-web-ui-stack.md).
