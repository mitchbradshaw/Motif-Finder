#!/usr/bin/env bash
# The stages after the chain grid, in order (docs/neurips_demo/README.md "Rebuilding the data"). Run from the demo
# worktree's root in Git Bash once precompute_chains.py has written all 108 x 12 results.
set -euo pipefail
cd "$(dirname "$0")/../.."
CONDA=/c/ProgramData/anaconda3/python.exe
VENV=../CNN/webui/.venv/Scripts/python.exe
n=$(ls DATA/neurips_demo/store/chains/*/*.json | wc -l)
if [ "$n" -ne 1296 ]; then echo "the grid is not complete: $n of 1296 results"; exit 1; fi
export PYTHONIOENCODING=utf-8
"$CONDA" scripts/neurips_demo/precompute_extras.py --stage manifest,seeds,stats 2>&1 | grep -v -i warning
"$VENV" scripts/neurips_demo/precompute_summaries.py
(cd webui/client && npx tsc -b && npx vite build --mode neurips) 2>&1 | grep -E "built|rror" || true
echo "store: $(du -sh DATA/neurips_demo/store | cut -f1)"
