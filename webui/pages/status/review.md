# Status — Review builder

| page | status | what's left | last commit |
|---|---|---|---|
| review.inspector | done | polish only; kit tick/band requests in requests/review.md | b547b37, 9fef5ed |
| review.cluster | done | members pager and the 50-member batch cap only exercised by code paths, fixtures have ≤ 7 members | 33837b5, 9fef5ed |

Routes: `#/review` → current unit of the last queue (q-12 c-0343) · `#/review/queue/<q>` → current unit · `#/review/queue/<q>/<item>` inspector ·
`#/review/queue/<q>/cluster/<n>` cluster · `#/review/cluster/<n>` alias · `#/review/queue/<q>?state=empty|exhausted` queue end.

States (deep links): 1 candidate (default) · 1b `?pop=other-channels` · 3 `?rail=queue` · 4 `?rail=evidence` (`?rail=both`) · 5 blind: any item of q-18/q-19 (`#/review/queue/q-19/w-40211`) ·
6 `?state=promoted` · 7 `#/review/queue/q-15/cluster/12?state=undone` · extras `?pop=queues|blind|shortcuts`, `?modal=unblind`, `?member=`, `?include=all`, `?pad=30|120|300`.

Keys: S I N A U, Space, 1–4, 9, Ctrl Z, Ctrl Shift Z (Ctrl Y), Enter (confirm promotion), ← → (items; members inside a cluster), E, \ (both rails).

Smoke: `smoke.py --pages-only --only review` → 32 states, 0 failures.
