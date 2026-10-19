#!/bin/bash
# Free cluster space by deleting what the PC already holds, checked file by file (scripts/rq4_cleanup.py).
# Each line of HPC/Detection/generated/rq4_batch3/cleanup_copied.txt is a path and the bytes the PC holds of it (0 = a work/ folder, which stays here). A
# finished task keeps its result.json, so the packs still see it as done; only its cache and work folders go.
#
#   bash HPC/Detection/generated/rq4_batch3/cleanup_copied.sh            dry run: what exists and how big
#   bash HPC/Detection/generated/rq4_batch3/cleanup_copied.sh --apply    delete exactly the listed paths
#
# Only paths under HPC/Detection/generated/rq4_ that lie inside a *_out/ folder are ever deleted.
set -euo pipefail
LIST=HPC/Detection/generated/rq4_batch3/cleanup_copied.txt
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
N=0; GONE=0; KB=0
while read -r P _BYTES; do
    [ -n "$P" ] || continue
    case "$P" in HPC/Detection/generated/rq4_*/*_out/*) ;; *) echo "refused (outside the sweep folders): $P"; continue;; esac
    case "$P" in *..*) echo "refused (..): $P"; continue;; esac
    [ -e "$P" ] || continue
    N=$((N + 1)); KB=$((KB + $(du -sk -- "$P" | cut -f1)))
    if [ "$APPLY" -eq 1 ]; then rm -rf -- "$P"; GONE=$((GONE + 1)); fi
done < "$LIST"
if [ "$APPLY" -eq 1 ]; then
    echo "deleted $GONE paths, $((KB / 1024)) MB freed"
else
    echo "dry run: $N listed paths exist here, $((KB / 1024)) MB; run with --apply to delete them"
fi
