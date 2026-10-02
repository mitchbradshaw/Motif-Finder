# fixup-L evidence — the gate's sandbox copy

Runtime `C:\Users\mmebr\Documents\CNN\webui\runtime\20261003-091114` (gitignored; the real database was never open).

## The adjudications row the walk wrote (`I` on the first item)

| id | detection | verdict | run | recording | run group | surrogate_of_run_id | start_idx | end_idx | score |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1208 | interesting | 84 | 1 | 3 | None | 298754 | 298766 | 8.43659782409668 |
| 2 | 102 | interesting | 32 | 385 | None | None | 2333 | 2393 | 0.09669756889343262 |

Row 1 is the walk's: detection 1208 of run 84, a real run (`surrogate_of_run_id` NULL) in queue 4's `run_ids`.
Row 2 is written later by the page-state walk's own Review state (*verdict given (I) writes to the database*,
queue 2 item 102) and is not part of this ticket's walk. `annotations` is untouched by either.

## The review_queues rows

| id | name | source_kind | source_ref | writes_to | filters_json |
|---|---|---|---|---|---|
| 1 | Library - extract events | extract-events | None | annotations | `None` |
| 2 | drop_detection_v1 - Mushroom_260720 CH14 | discovery-run | None | adjudications | `{"run_id": 32}` |
| 3 | mp_threshold · run #80 | discovery-run | None | adjudications | `{"run_id": 80}` |
| 4 | Discovery · mp_threshold | discovery-run | None | adjudications | `{"run_ids": [84, 86]}` |
| 5 | Discovery · smoke_seed | seed-search | None | adjudications | `{"run_ids": [88, 90]}` |

## The run groups those queues' runs belong to — what a group-keyed queue would have served

**run group 3** — real detections 3, surrogate detections 1

| run | recording | surrogate_of_run_id | detections |
|---|---|---|---|
| 84 | 1 | None | 1 |
| 85 | 1 | 84 | 1 |
| 86 | 2 | None | 2 |
| 87 | 2 | 86 | 0 |

**run group 4** — real detections 132, surrogate detections 136

| run | recording | surrogate_of_run_id | detections |
|---|---|---|---|
| 88 | 1 | None | 67 |
| 89 | 1 | 88 | 68 |
| 90 | 2 | None | 65 |
| 91 | 2 | 90 | 68 |

## Descriptor in `discovery_sessions.state_json`

session 1: absent, session 2: absent

## What the smoke recorded

```json
{
  "fixup_l": {
    "toast": "3 unjudged in 'Discovery · mp_threshold' · verdicts write adjudications\nOpen Review",
    "queue": {
      "id": 4,
      "name": "Discovery · mp_threshold",
      "source_kind": "discovery-run",
      "writes_to": "adjudications",
      "unit": "detection",
      "total": 3,
      "judged": 0,
      "remaining": 3,
      "filters": {
        "run_ids": [
          84,
          86
        ]
      }
    },
    "adjudications_written": [
      {
        "id": 1,
        "detection_id": 1208,
        "verdict": "interesting",
        "created_at": "2026-10-02T23:13:29.119771+00:00",
        "run_id": 84,
        "surrogate_of_run_id": null
      }
    ],
    "score_row_before": "mp_threshold\n\t3\t0\t0\t0\tno detections in the reviewed overlap\t0.00 over 2 h\t1 / 2\t3.0×",
    "score_row_after": "mp_threshold\n\t3\t0\t0\t0\tno detections in the reviewed overlap\t0.00 over 2 h\t1 / 2\t3.0×",
    "seed_queue": {
      "id": 5,
      "name": "Discovery · smoke_seed",
      "source_kind": "seed-search",
      "source_ref": null,
      "unit": "detection",
      "writes_to": "adjudications",
      "blind": 0,
      "cap": null,
      "verdict_options": null,
      "filters_json": "{\"run_ids\": [88, 90]}",
      "created_at": "2026-10-02T23:13:39+00:00",
      "closed_at": null,
      "note": "Discovery run 'smoke_seed' (smoke_seed) · session 2 · runs 88, 90",
      "filters": {
        "run_ids": [
          88,
          90
        ]
      },
      "total": 110,
      "judged": 0,
      "remaining": 110,
      "pace_s": null
    }
  },
  "pass_to_review": {
    "label": "→ Pass 2 to Review",
    "headline": "last run · 2 spans · mean 9.0 s",
    "landed": "#/review/queue/3/1206",
    "progress": "0 / 2\npace not yet measured"
  }
}
```
