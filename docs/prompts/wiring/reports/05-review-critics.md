# Critics' record - Prompt 05 (Review), stage 2

Three critics, Opus at medium effort, disjoint briefs, run 2026-09-22 against a **sandbox** bridge on
8765 whose database was a copy of the project database with both seeded queues in it
(`webui/runtime/20260922-103011/annotations.sqlite`).

They were run against the sandbox rather than `--project` on purpose. Two of the three must write
verdicts to do their job, and `adjudications` is empty on this machine: machine-generated critic verdicts
in the real table would be indistinguishable from genuine ones afterwards and would poison the RQ5
divergence measurement - the same failure mode `requests/04-to-05.md` §2 raises about bulk discards. The
sandbox copies the real database, so they still exercised real queues over real detections and real
sequences; only their writes were thrown away.

| Critic | Score | Findings |
|---|---|---|
| Function | **1 / 10** | 7 (3xP0, 2xP1, 1xP2, 1xP3) |
| Data-truth | **4 / 10** | 8 (1xP0, 3xP1, 2xP2, 2xP3) |
| Write-safety | **3 / 10** | 11 (3xP0, 2xP1, 3xP2, 3xP3) |

The scores are low and they are earned. What they mean in one line each: the **write paths are sound in
their shape but wrong on real ids**; the **page did not render at all**; the **read numbers are exactly
right and the write numbers are not**.

## P0 - wrong data written, a rule-5 crossing, or data loss  (7)

### Every live Review item crashes the whole Review workspace: `d.artifact.level` on a payload where the bridge always sends artifact: null

*Function critic* - `webui/client/src/review/Inspector.tsx:174 and :180 (also ClusterView.tsx:210); bridge side webui/server/review.py:212 `"artifact": item.get("artifact")``

**Reproduce**

```
Open http://127.0.0.1:8765/#/review/queue/2/101 (or /queue/1, or /queue/2, or /review/cluster/1) in a browser and reload. Confirm the payload with: GET http://127.0.0.1:8765/api/review/queues/2/items/101 -> "artifact": null.
```

**Expected** The inspector paints: context trace, shape card, nearest families, the micro-stat pills, and the keymap is live.

**Actual** The React error boundary replaces the entire workspace with the red card "⚠ review workspace failed to render — Cannot read properties of null (reading 'level')", plus two console errors (`TypeError: Cannot read properties of null (reading 'level')` and `[render error in review workspace] ...`). Nothing else paints — no queue picker, no rail, no progress, no inspector. `Working/review/*.py` never sets an `artifact` key on any item for any queue kind, so `item.get("artifact")` is None unconditionally; this is 100% of live items, not an edge case. The TS type `ItemDetail.artifact: ArtifactFactors` is non-optional and the bridge value is cast through `raw?.artifact` (any), so `npx tsc -b` cannot catch it.

**Why it matters** The Review workspace is completely unusable on real data. No verdict can be given through the UI at all. This alone makes stage-2 item 2 (the smoke gate) impossible to pass honestly.

### The keyboard fast path is unreachable — S / I / N / A / U / Space / Ctrl-Z do nothing on live data

*Function critic* - `webui/client/src/review/keys.ts (useReviewKeys is mounted inside the crashed subtree, Inspector.tsx:155-167)`

**Reproduce**

```
Navigate to http://127.0.0.1:8765/#/review/queue/2/101, wait for load, then press `s`, then `i`, then `Space`. Re-read document.body.innerText and location.hash.
```

**Expected** `s` writes verdict seed (and opens the promotion confirm), `i` writes interesting, Space advances without writing, Ctrl-Z undoes, and auto-advance moves the hash to the next item id.

**Actual** Nothing happens. location.hash stays #/review/queue/2/101, the page text stays the render-error card, no /api/review/.../verdict request is made (browser_network_requests shows only GET queues/2 and GET queues/2/items/101). The keymap is registered by a component inside the boundary that failed, so the window keydown listener was never attached. I could not test a single one of the five verdict keys, Space, or Ctrl-Z on the real UI.

**Why it matters** Spec §10.3 makes the keyboard the fast path through a queue; a researcher cannot get through a single item, let alone 160.

### The seed/promote path will crash the same way once `artifact` is fixed: `d.nearest[0]` is dereferenced unguarded and the bridge always sends nearest: []

*Function critic* - `webui/client/src/review/Inspector.tsx:224 (`overlay || d.nearest[0].id`), :229, :75 (`d.nearest[0].d` on verdict 'seed'); webui/client/src/review/parts.tsx:288-290; bridge webui/server/review.py:210-211`

**Reproduce**

```
GET http://127.0.0.1:8765/api/review/queues/2/items/101 -> "nearest": [], "medoids": {}. Same for queue 1 item 119. `grep -rn 'nearest\|medoid' Working/review/*.py` returns nothing, so the core never populates either key.
```

**Expected** Fixing the null-artifact deref lets the inspector render and S promote.

**Actual** It will not. Inspector.tsx:224 runs on every item inside the `d && !d.refused` block and evaluates `d.nearest[0].id` on an empty array -> `Cannot read properties of undefined (reading 'id')`. The nearest-families card and the promotion dialog (parts.tsx:288, `nearest.d`) fail identically. I am reporting this as a second defect rather than a consequence because whoever fixes finding 1 will otherwise hit it immediately and think the fix regressed.

**Why it matters** Two independent unconditional crashes sit on the same render path; fixing one does not make the page usable, so a stage-2 fix-and-re-run that only guards `artifact` will still fail the gate.

### An extract-events verdict overwrites an unrelated human annotation whose id happens to equal the sequence id

*Data-truth critic* - `Working/review/verdicts.py:86 `_check_target` / :136 `_write_annotation` (reached via webui/server/review.py:427 POST /api/review/queues/{qid}/verdict and :505 /extract)`

**Reproduce**

```
Against the sandbox bridge: `POST http://127.0.0.1:8765/api/review/queues/1/verdict {"target_id":120,"verdict":"interesting","note":"data-truth critic q1"}`. Queue 1 is the seeded `Library - extract events` queue (unit=sequence, writes_to=annotations); target 120 is SEQUENCE id 120. Then in the sandbox DB: `SELECT * FROM annotations WHERE id=120;` and `SELECT * FROM sequences WHERE id=120;`
```

**Expected** The write lands on (or is refused for) sequence 120 — sequence_key 'human_r1_ch0_1132013s', recording 1, samples 1132013-1140592. No pre-existing human annotation is altered.

**Actual** HTTP 200. `annotations` row id 120 — recording 1, samples 694200-694800, source 'imported_10min', created 2026-08-03, a completely different span — had its verdict set and its note overwritten to 'data-truth critic q1'. The sequence row was untouched and still has needs_extraction=1. `_check_target` only asks `SELECT 1 FROM annotations WHERE id = ?`, so a sequence id that collides with an annotation id passes the rule-5 gate; it never checks that the target is actually in the queue's resolved source. In this database ALL 30 sequence ids of the seeded queue (119-148) collide with existing annotation ids (verified: 30 of 30), so every item of that queue corrupts a different human row. The same happens through /extract: audit rows 15-17 (another critic) all landed on annotation 122, stamping a JSON blob and then 'extraction complete' into its note, and created no child annotation with parent_annotation_id.

**Why it matters** This writes a fabricated human verdict and note into the human table, on a row nobody reviewed, and destroys the note that was there. In --project mode this is the real research record. It also silently loses the reviewer's actual work: the sequence never gets its events and never loses needs_extraction.

### An extract-events verdict writes to annotations.id using a sequences.id — it silently rewrites an unrelated human annotation

*Write-safety critic* - `Working/review/queues.py:_resolve_sequences (~line 445) vs Working/review/verdicts.py:_check_target / _write_annotation`

**Reproduce**

```
curl -X POST http://127.0.0.1:8765/api/review/queues/1/verdict -H 'Content-Type: application/json' -d '{"target_id":119,"verdict":"not_interesting","note":"critic test 2"}'  then read the sandbox DB: SELECT id,recording_id,start_idx,end_idx,verdict,note FROM annotations WHERE id=119; and SELECT id,recording_id,start_idx,end_idx,annotation_id FROM sequences WHERE id=119;
```

**Expected** The verdict lands on the annotation that IS sequence 119 — sequences.annotation_id = 11266 (recording 1, 1209600-1245600) — or is refused.

**Actual** HTTP 200. annotations.id=119 changed from verdict 'interesting', note NULL to verdict 'not_interesting', note 'critic test 2'. That row is recording 6, samples 229000-229600, source 'imported_10min' — a completely different human observation that was never in any queue. _resolve_sequences hands out target_id = sequences.id; _check_target only asks 'does an annotations row with this id exist', and in this database every sequence id (119-148) also exists as an annotation id, so the collision is total.

**Why it matters** Every verdict a reviewer gives on the seeded 'Library - extract events' queue corrupts a random pre-existing human annotation and leaves the intended one untouched. This is silent, irreversible-looking corruption of the human research record — rule 5's table is right but the ROW is wrong.

### Rule 5 detection->annotations is not enforced when the id exists in both tables (i.e. for every detection in this database)

*Write-safety critic* - `Working/review/verdicts.py:_check_target`

**Reproduce**

```
curl -X POST http://127.0.0.1:8765/api/review/queues/1/verdict -H 'Content-Type: application/json' -d '{"target_id":100,"verdict":"seed","note":"RULE5 detection id into annotations queue"}'  (detection 100 exists: run_id 32, 2380-2440). Then SELECT id,verdict,note FROM annotations WHERE id=100;
```

**Expected** 409 PermissionError naming rule 5, and no row written in either table (this is exactly the check the stage-1 report claims in §4).

**Actual** HTTP 200. annotations.id=100 (recording 6, start 237600) went from verdict 'interesting', note NULL to verdict 'seed', note 'RULE5 detection id into annotations queue'. _check_target for writes_to='annotations' tests _is_annotation FIRST and returns as soon as a row with that id exists in annotations; it only reaches the PermissionError branch if the id is absent from annotations. detections ids here run 1..732 and annotations 1..11269, so the refusal branch is unreachable for every real detection id. The mirror direction has the same shape (_is_detection first) and is equally dead for any annotation id <= 732 — annotation 500 and detection 500 both exist.

**Why it matters** The rule-5 guard the whole design rests on is decorative on this data. The only reason my annotation->adjudications test was refused is that I picked id 11266, which is outside the detections id range. A check that passes only when the ids happen not to collide is not a check.

### POST /extract creates no annotations at all: the extracted events are lost and the parent's note is clobbered

*Write-safety critic* - `webui/server/review.py:post_extract (~line 515)`

**Reproduce**

```
curl -X POST http://127.0.0.1:8765/api/review/queues/1/extract -H 'Content-Type: application/json' -d '{"sequence_id":122,"events":[{"start_idx":1749500,"end_idx":1749560},{"start_idx":1750000,"end_idx":1750060}],"complete":true}'  then: SELECT COUNT(*) FROM annotations; SELECT id,verdict,note FROM annotations WHERE id=122; SELECT id,parent_annotation_id FROM annotations WHERE parent_annotation_id IN (122,11271); SELECT needs_extraction FROM sequences WHERE id=122;
```

**Expected** Per the stage-1 report §5 and §2: one NEW singular annotation per event, each with parent_annotation_id pointing at the parent sequence's annotation (11271), and sequences.needs_extraction cleared to 0 because complete=true.

**Actual** HTTP 200 but the annotations count is unchanged at 11269 — zero new rows. No parent_annotation_id was set anywhere (the only child row, 11272, pre-dates the call). Instead each event was serialised into the NOTE of annotation 122 (again the wrong row — sequence 122's annotation is 11271), each event overwriting the previous one, and then 'extraction complete' overwrote both: annotation 122 ends up with note='extraction complete' and nothing survives of either event. sequences.needs_extraction is still 1, so the item never leaves the queue. The single gesture also produced THREE review_audit rows (15, 16, 17), so it takes three Ctrl-Z to walk back.

**Why it matters** Item 8 of the write-safety brief fails completely: the reviewer's extraction work is discarded, the parent sequence's annotation note is destroyed, and the queue can never drain. This is data loss on the human table.

## P1 - a core flow is broken or a count is wrong  (7)

### The default #/review landing goes to fixture queue id 'q-12', which does not exist live — and its only escape button navigates back to it

*Function critic* - `webui/client/src/review/index.tsx:26 (`useDemoState<string>('review.lastQueue', () => 'q-12')`), :30, :74`

**Reproduce**

```
Open http://127.0.0.1:8765/#/review with a clean profile.
```

**Expected** The landing route resolves to a live queue (id 1 or 2) or shows a queue picker listing both seeded queues.

**Actual** The hash is rewritten to #/review/queue/q-12, the bridge 404s (`GET /api/review/queues/q-12 => 404`, console error `read failed p: no review queue 'q-12'`), and the page shows the red card "Queue q-12 failed to load / no review queue 'q-12'". Live queue ids are integers 1 and 2. The `Unknown` fallback's only action button is labelled "Open Discovery · r-0412" and calls navigate('review/queue/q-12') — i.e. straight back into the same 404.

**Why it matters** The front door of the workspace is a dead end on real data, and I could not verify checklist item 1 (a queue picker listing both queues with real counts) because no picker ever paints.

### The header's "N need you" is a fixture constant (3) and never reads /api/review/counts (which says 160)

*Function critic* - `webui/client/src/shell/Header.tsx:43 (`DEMO_NEED_YOU` from webui/client/src/fixtures/canon.ts:122)`

**Reproduce**

```
Load any page on http://127.0.0.1:8765 and read the header chip; then GET http://127.0.0.1:8765/api/review/counts. Also list network requests filtered on /api/ across several navigations.
```

**Expected** The chip reads 160 (30 extract-events + 130 detections), matching the two seeded queues.

**Actual** The chip reads "● 3 need you". `/api/review/counts` is never requested by the client on any route I visited — the route exists and is correct, but nothing consumes it. The number shown is DEMO_NEED_YOU plus this tab's own failed runs.

**Why it matters** Checklist item 8 fails: the header lies about how much work is waiting, by a factor of 50, and it is the one number a researcher sees on every page.

### An annotations/sequence queue never registers `judged` — remaining never decreases

*Data-truth critic* - `Working/review/queues.py:487 `_audit_judged_ids` vs Working/review/verdicts.py:302 (payload shape)`

**Reproduce**

```
`GET /api/review/counts` and `GET /api/review/queues` (queue 1) before and after `POST /api/review/queues/1/verdict {"target_id":120,"verdict":"interesting"}`. Then `SELECT payload_json FROM review_audit WHERE queue_id=1;`
```

**Expected** After a successful verdict, queue 1 judged 0 -> 1, remaining 30 -> 29, header 293 -> 292.

**Actual** Unchanged: total=30, judged=0, remaining=30, header 293 both sides — after SIX successful audit rows (ids 4, 5, 15, 16, 17, 27). `_audit_judged_ids` reads `payload.get("target_id")` and `payload.get("target_ids")`, but `write_verdict`/`write_batch` emit `{"writes_to":..., "verdict":..., "targets":[{"target_id":120, ...}]}` — neither key the reader looks for exists, so the set is always empty. (The id IS present in the separate `review_audit.target_ids` COLUMN, which the reader ignores.)

**Why it matters** The report's own §9.4 warns that a writer bypassing the audit ledger strands spans in their queue forever; the writer and the reader disagree about the ledger's shape, so every annotation-writing queue is stranded from day one. The queue can never be worked down and 'N need you' never falls.

### Held-out detections are counted into total and into "N need you" but never served as rows

*Data-truth critic* - `webui/server/review.py:344 get_queue (held-out row filter) vs Working/review/queues.py:200 queue_counts / :219 header_counts`

**Reproduce**

```
`POST /api/review/queues {"name":"CRITIC heldout test","source_kind":"discovery-run","filters":{"run_id":4}}` — run 4 is on recording 49 = M4_aug_concat_fs1.mat, the held-out file, and has 11 detections. Then `GET /api/review/queues/<id>` and `GET /api/review/counts`.
```

**Expected** Either the queue is refused at creation, or its total/remaining are 0 — a held-out item that cannot be reviewed is not part of the question being put.

**Actual** total=11, judged=0, remaining=11, but `rows` served = 0 (the route filters held-out rows out). The header went from 290 to 301, i.e. +11 items the researcher is told they must judge and is never shown. `queue_counts`/`header_counts` have no held-out filter at all.

**Why it matters** A permanently non-zero, unclearable badge: total != rows served, and 'N need you' can never reach zero. It is also a count that disagrees with what the same endpoint serves one field away.

### A verdict on a held-out detection is accepted and written to adjudications

*Data-truth critic* - `webui/server/review.py:427 post_verdict (no held-out check on the write path)`

**Reproduce**

```
With the queue from the previous finding: `POST /api/review/queues/<id>/verdict {"target_id":2,"verdict":"interesting","note":"critic heldout"}` (detection 2 belongs to run 4 on recording 49, M4_aug_concat_fs1.mat). Then `SELECT * FROM adjudications WHERE detection_id=2;`
```

**Expected** 409/400 carrying the same D6 refusal the read routes give ('...is held out (D6): it is locked for the final evaluation and cannot be reviewed...'). CLAUDE.md: 'M4_aug_concat_fs1.mat is refused on every route.'

**Actual** HTTP 200, `{"verdict": {..."audit_id": 18...}, "counts": {"total":11,"judged":1,"remaining":10}}` and adjudications row id 17 written for detection 2. The GET item route on the very same id correctly returns `refused`, so read and write disagree.

**Why it matters** Contaminates the held-out evaluation set with human labels. The read routes are careful about exactly this and the write route is not, so the protection is one POST away from being bypassed.

### Undo after a promotion reports success but reverses nothing, and burns the audit row so it can never be reversed

*Write-safety critic* - `Working/review/verdicts.py:undo_last (writes_to falls back to row['target_table']='motif_member') + webui/server/review.py — there is no unpromote route`

**Reproduce**

```
POST /api/review/queues/2/promote {"target_id":111,"verdict":"seed"} (gave entry 3611, member 3606), then POST /api/review/queues/2/undo, then SELECT id FROM motif_entry WHERE id=3611; SELECT id FROM motif_member WHERE id=3606; SELECT * FROM adjudications WHERE detection_id=111; SELECT id,action,undone_at FROM review_audit ORDER BY id DESC LIMIT 2;
```

**Expected** Ctrl-Z on a promotion removes both halves (P21) — or, if the generic undo route cannot, it refuses.

**Actual** HTTP 200 {'undone': {'audit_id':26,'action':'promote','writes_to':'motif_member'}} and the table diff was EMPTY: motif_entry 3611, motif_member 3606, motif_member_revision and adjudications(111) all still present. undo_last has no 'motif_member' branch, so it stamps undone_at and returns. POST /queues/2/unpromote is 404 — promotion.unpromote() is unreachable from the bridge. Pressing undo a second time then reverses audit 25 (the promotion's own verdict), deleting adjudications(111) and leaving motif_member 3606 / motif_member_revision(detection_id=111) in the Library with no verdict behind them.

**Why it matters** A reviewer who promotes by mistake cannot take it back, is told they have, and a second press leaves a Library motif whose originating judgement no longer exists — a fabricated entry in the very store P21 says only a human verdict may create.

### An annotation/sequence queue never registers anything as judged, so it never drains and 'N need you' never falls

*Write-safety critic* - `Working/review/queues.py:_audit_judged_ids (~line 494) vs Working/review/verdicts.py:write_verdict/write_batch payload shape`

**Reproduce**

```
POST /api/review/queues/1/verdict {"target_id":119,...} (200), then GET /api/review/queues/1 and GET /api/review/counts. Also: SELECT payload_json FROM review_audit WHERE id=4;
```

**Expected** queue 1 total 30 / judged 1 / remaining 29, and the header count drops.

**Actual** total 30 / judged 0 / remaining 30, after SIX un-undone audit rows on queue 1 (ids 4,5,15,16,17,27). _audit_judged_ids looks for payload['target_id'] and payload['target_ids'], but write_verdict/write_batch write neither — their payload is {'writes_to','verdict','note','window_set_id','window_index','targets':[{'target_id':...}]}. The key it reads is never written, so the set is always empty.

**Why it matters** Every annotation-writing queue (explore-spans and extract-events, two of the six kinds) is a queue the reviewer can never finish: judged items keep reappearing and the header badge is permanently wrong. §9.4 of the report already warns that a writer bypassing the ledger strands spans forever — the ledger's own writer is that bypasser.

## P2 - wrong but recoverable  (6)

### Live Review pages are badged "demo data"

*Function critic* - `webui/client/src/review/index.tsx:71 (`<Header workspace="Review" page="Inspector" demo />`)`

**Reproduce**

```
Open http://127.0.0.1:8765/#/review — document.body.innerText contains "demo data" while the page is in fact reading the live bridge.
```

**Expected** No demo badge on a wired page, or the badge driven by whether the data actually came from a fixture.

**Actual** The badge is hardcoded on the Review header, so a wired page labels its real content as demo. (Inverse of the usual risk, but still a page telling the researcher something untrue about its own provenance.)

**Why it matters** The badge is the UI's own claim about whether what you are looking at is real; if it is hardcoded it cannot be trusted anywhere.

### A soft-deleted human span still suppresses a detection from the queue and from the counts

*Data-truth critic* - `Working/review/queues.py:315 `_annotations_by_recording` (and :400 `_resolve_spans`) — no `deleted_at IS NULL` filter`

**Reproduce**

```
Insert `INSERT INTO annotations (recording_id,start_idx,end_idx,verdict,source,created_at) VALUES (385,48,108,'interesting','critic-test','2026-09-22')` (an exact match to detection 618 of run 32). Queue 2 goes 130/2/128 -> 129/2/127, header 158 -> 157, and 618 leaves the rows — correct. Now `UPDATE annotations SET deleted_at='2026-09-22' WHERE id=<that id>` and re-read.
```

**Expected** Deleting the span un-suppresses detection 618: total back to 130, remaining 128, header 158.

**Actual** Unchanged — total 129, remaining 127, 618 still absent. Every other reader in the codebase filters soft-deleted rows (`Working/database/queries.py:271,359,427`, `Working/discovery/scoreboard.py:89`, `webui/server/corpus.py:158,211,237,259`, `webui/server/explore_routes.py:88`, `Working/library/importers/annotations.py:178`); `Working/review/queues.py` is the one that does not.

**Why it matters** A candidate is silently withheld from the researcher, and the count is short by one, on the strength of a span they deleted. Recoverable (undelete restores it) but the queue is lying about what is left.

### The cap is consumed by rediscoveries: a capped queue can serve fewer items than its cap while candidates remain

*Data-truth critic* - `Working/review/queues.py:233 `_resolve` (cap applied before the prior-verdict filter) vs :200 queue_counts (filter applied after)`

**Reproduce**

```
Create a cap=5 queue over run 32 (`POST /api/review/queues {"source_kind":"discovery-run","cap":5,"filters":{"run_id":32}}`) — it reports total=5, rows [100,101,102,103,104]. Now insert an annotation on recording 385 at 5470-5530, an exact match to detection 101, and re-read the queue.
```

**Expected** total stays 5 — the queue asks about five things, and there are 125 unasked candidates to fill the gap.

**Actual** total=4, judged=1, remaining=3, rows [100,102,103,104]. The cap slices the source first, then the rediscovery is removed from inside the slice.

**Why it matters** 'Cap at N' silently becomes 'at most N', and the shortfall is invisible — a sampling queue meant to put N questions puts fewer, which biases any precision figure computed from it.

### Cluster accept/reject is dead code: no resolver ever emits a cluster number, so every cluster route 404s

*Write-safety critic* - `webui/server/review.py:_clusters (~line 353) and the three /cluster routes`

**Reproduce**

```
GET /api/review/queues/2?include_judged=1 -> "clusters": [] (same for queue 1). POST /api/review/queues/2/cluster/0/accept -> 404 'no cluster 0 in queue 2'. grep -rn 'cluster_no|clusterNo' Working/review/ webui/server/review.py returns only the two lines inside _clusters itself.
```

**Expected** Item 7 of the brief: a cluster accept writes verdicts for its members under one audit row.

**Actual** _clusters reads it.get('clusterNo', it.get('cluster_no')) off queue items, and none of _resolve_detections / _resolve_spans / _resolve_sequences / _resolve_windows ever puts either key on an item. The dict is always empty, so GET /cluster/{no}, /cluster/{no}/accept and /cluster/{no}/reject can only ever 404.

**Why it matters** A whole documented flow is unreachable and untestable on real data. Nothing is written wrongly, but the §5 claim that 'a cluster's members are judged under one audit row' is not exercised by anything.

### A verdict is accepted for a target that is not in the queue, and the audit row attributes it to that queue

*Write-safety critic* - `Working/review/verdicts.py:write_verdict / write_batch (no membership check) — called from webui/server/review.py:post_verdict`

**Reproduce**

```
GET /api/review/queues/2 shows 130 ids, all detections of run 32 (100..629). Then POST /api/review/queues/2/verdict {"target_id":700,"verdict":"seed"} — detection 700 belongs to run 34. Also 710 (run 44) via /batch.
```

**Expected** 400/409, or at least a refusal to file a verdict against a queue that never asked about the item.

**Actual** HTTP 200; adjudications rows written for detections 700-704 and 710-714, each with a review_audit row carrying queue_id=2. The queue's own item list never contained them.

**Why it matters** The audit ledger — the thing undo and the judged-set are built on — records that queue 2 asked about detections it never showed anyone. A client bug or a stale id in the browser writes verdicts into runs the reviewer was not looking at, and the provenance trail says otherwise.

### Any verdict carrying tags 500s: the bridge sends a list, both core writers expect a dict

*Write-safety critic* - `webui/server/review.py:VerdictBody.tags (list[str]) vs Working/review/verdicts.py:_write_annotation (tags.items()) and Working/database/adjudications.insert_adjudication`

**Reproduce**

```
POST /api/review/queues/2/verdict {"target_id":106,"verdict":"seed","tags":["aaa","bbb"]}  and POST /api/review/queues/1/verdict {"target_id":121,"verdict":"seed","tags":["ccc"]}
```

**Expected** 200, with adjudication_tags / annotation_tags rows written.

**Actual** HTTP 500 on both: "AttributeError: 'list' object has no attribute 'items'". Good news, and I checked it specifically: NO half-write — adjudications has no row for 106, adjudication_tags is empty, and annotation 121 kept its original verdict, because the failure precedes conn.commit() and the connection is closed without committing. Related but separate: undo of a TAGGED adjudication could not be exercised at all because of this, and reading _restore_adjudication shows it restores verdict and note only — a re-judge's undo would leave the newer tags in place. I could not confirm that on the running bridge.

**Why it matters** Tagging a verdict — part of the documented Review vocabulary — is broken end to end on every queue kind, and the tag half of undo is consequently unverified.

## P3 - polish  (6)

### Detection queues show non-zero `judged` the moment they are created, because `judged` is read from the shared adjudications table

*Function critic* - `webui/server/review.py GET /api/review/queues -> Working/review/queues.py queue_counts`

**Reproduce**

```
POST http://127.0.0.1:8765/api/review/queues {name:'…', source_kind:'discovery-run', blind:true, filters:{run_id:32}}. The response for the brand-new queue is total 130, judged 2, remaining 128.
```

**Expected** Arguably 0 judged on a queue nobody has worked yet.

**Actual** It inherits the judgements another queue over the same run already wrote. This is a defensible design (the detection table is authoritative), but it means "remaining" on a fresh queue is not the size of the work the person was actually asked to do, and it is worth a deliberate decision rather than a side effect.

**Why it matters** Progress and pace on a detection queue are computed from these numbers; I could not check them in the UI (P0-1) so this is the only handle on them.

### `prior_verdict` is computed but can never reach the client — no route exposes include_prior_judged

*Data-truth critic* - `webui/server/review.py:335 get_queue (only `include_judged` is a query param)`

**Reproduce**

```
`GET /api/review/queues/2?include_prior_judged=1` — the parameter is ignored; there is no route path that calls `queues_mod.queue_items(..., include_prior_judged=True)`. With the matching annotation in place, detection 618 is simply absent from every route's output.
```

**Expected** 04-to-05 §3 / spec §4.7: Review carries the prior verdict on a rediscovery and defaults to not re-asking — the researcher can still see it and override.

**Actual** The core computes prior_verdict/prior_annotation_id/prior_iou/prior_onset_gap correctly, but the bridge never serves them and offers no way to ask for them, so the 'carries that verdict' half of the request is unreachable through the UI. `_item_or_404` also 404s on such an id.

**Why it matters** Half of the cross-prompt request is implemented in the core and stranded there; the researcher has no way to review what was auto-excluded.

### Served `channel` is a derived electrode name that contradicts the queue's own title

*Data-truth critic* - `webui/server/review.py:151 `_entry_payload` (row['channel'] = rec['name'])`

**Reproduce**

```
`GET /api/review/queues/2` — every row has channel 'CH1'. The queue is named 'drop_detection_v1 - Mushroom_260720 CH14' and the recording is `Mushroom_260720_0509_4hrs_CH14_fs1.mat` (recordings.id=385, recordings.channel=0, notes 'ch 14 Xmas red; single-channel export').
```

**Expected** A channel label a reader can reconcile with the file — CH14, or at least not a different electrode number.

**Actual** 'CH1', derived from `channel_name(source_file, 0, 1)`. Not a database disagreement (the DB really says channel 0) but the row and the queue title name different electrodes.

**Why it matters** Cosmetic here, but a reviewer judging drops is being told which electrode they are looking at, and the two labels on the same screen disagree.

### create_queue accepts a writes_to that contradicts its source_kind, with no validation

*Write-safety critic* - `Working/review/queues.py:create_queue (~line 124, `writes_to or d_writes`)`

**Reproduce**

```
POST /api/review/queues {"name":"CRITIC wt annotations","source_kind":"discovery-run","source_ref":"32","writes_to":"annotations"} -> 200, queue id 7 with unit='detection' and writes_to='annotations'.
```

**Expected** A refusal, or at minimum unit and writes_to forced to agree. The report calls writes_to 'the rule-5 decision made once, at creation, where a person can read it'.

**Actual** Accepted silently. That queue's resolver hands out detection ids while its verdicts write annotations — precisely the crossing rule 5 forbids, created through the public route. I could not make it write anything because source_ref='32' resolves to zero items for discovery-run (it keys on run_group_id, not run id), so this is latent rather than demonstrated; the same crossing is already live on queue 1 by a different route.

**Why it matters** The one place the rule-5 decision is supposed to be made carefully accepts an arbitrary override from an HTTP body.

### Empty and duplicate-id batches are accepted and audited

*Write-safety critic* - `Working/review/verdicts.py:write_batch`

**Reproduce**

```
POST /api/review/queues/2/batch {"target_ids":[],"verdict":"seed"} -> 200, count 0, audit row 28 written with target_ids '[]'. POST {"target_ids":[117,117,117]} -> 200, count 3, one adjudications row, audit says 3 targets.
```

**Expected** An empty batch is a no-op that writes no audit row; a duplicate id is collapsed.

**Actual** An audit row is written for an act that touched nothing, and the batch result reports count 3 for one row written.

**Why it matters** Minor ledger noise, and the reported count is what the UI shows the reviewer ('5 judged') when the truth is 1.

### A CHECK-constraint violation on queue creation surfaces as a 500 traceback, not a 400

*Write-safety critic* - `webui/server/review.py:post_queue / _core_call (catches ValueError and KeyError, not sqlite3.IntegrityError)`

**Reproduce**

```
POST /api/review/queues {"name":"x","source_kind":"discovery-run","writes_to":"detections"}
```

**Expected** 400 with the constraint explained.

**Actual** 500 with 'IntegrityError: CHECK constraint failed: writes_to IN (...)' and a full traceback. It is loud, which CLAUDE.md wants, but it is a client input error reported as a server fault.

**Why it matters** Cosmetic; noted only because the same _core_call gap would turn any future IntegrityError into a 500 rather than a refusal the researcher can read.

## What the critics verified as CORRECT

This half matters as much as the findings: it is the part of the stage-1 work that survived contact with
real data and an adversary.

### Function critic

- Bridge data is real and non-fake: GET /api/review/queues returns both seeded queues with total/judged/remaining = 30 (extract-events, writes_to=annotations, unit=sequence) and 130 (discovery-run run_id 32, writes_to=adjudications, unit=detection). GET /api/review/counts returns need_you=160 = 30+130.
- Item payloads carry genuine data: /api/review/queues/2/items/101 returns a 638-point context trace with t0_s, a 60-point shape trace, a 40-point thumb, real start/end sample indices and a real detector score (0.0633). Nothing is synthesised.
- P20 blinding is structurally correct, not cosmetic. I created a blind queue through the API (POST /api/review/queues, blind:true, id 4) and read the JSON off the wire: the `score` key is ABSENT from every row of GET /api/review/queues/4 and from `entry` of GET /api/review/queues/4/items/100, and `evidence.detection` is null. On the non-blind queue 2 the same keys are present. The score genuinely does not reach the browser.
- The bridge fails loudly rather than blankly: GET /api/review/queues/q-12 is a 404 with the message "no review queue 'q-12'" and the client renders a red error card with that text, not an empty page.
- No 500s were observed from the bridge on any route I hit.
- The keymap source (webui/client/src/review/keys.ts) does implement the spec §10.3 mapping I was asked to test — s/i/n/a/u -> seed/interesting/not_interesting/artifact/unsure, Space -> skip, Ctrl-Z -> undo, arrows -> next/prev, suppressed while typing. I could not exercise it (see P0-1).

### Data-truth critic

- Queue 1 'Library - extract events': route says total=30, judged=0, remaining=30; SQL `SELECT COUNT(*) FROM sequences WHERE needs_extraction=1` = 30. Agrees, and total = judged + remaining.
- Queue 2 'drop_detection_v1 - Mushroom_260720 CH14': route says total=130, judged=0 (at first read), remaining=130; SQL `SELECT COUNT(*) FROM detections WHERE run_id=32` = 130, `adjudications JOIN detections WHERE run_id=32` = 0. Agrees.
- GET /api/review/counts 'need_you' equals the sum of `remaining` over open queues on every reading (e.g. 160 = 30+130; later 280 = 30+125+125+0).
- Writing one verdict (detection 629) moved queue 2 from 130/1/129 to 130/2/128 and the header from 159 to 158 — exactly one, right direction, in both the queue detail and the header — and SQL confirmed adjudications-on-run-32 went 1 -> 2.
- Superseded-run filter (04-to-05 §2): setting `runs.superseded_at` on run 32 made queue 2 go to total=0/judged=0/remaining=0 with 0 rows and dropped the header from 158 to 30 (exactly the 128 remaining). Clearing it restored 130/2/128 and header 158. Verified against the data, not the code.
- Prior-verdict rule (04-to-05 §3) positive case: inserting an annotation on recording 385 at 48-108 (exact match to detection 618) removed 618 from the queue, total 130 -> 129, remaining 128 -> 127, header 158 -> 157. Deleting the annotation restored all three.
- Prior-verdict rule uses the ONSET term, not IoU alone: an annotation at 14337-14397 against detection 179 (14321-14381) has interval_iou = 0.5789 (passes the 0.5 half) but onset gap 16 > 0.25*60 = 15, and detection 179 correctly stayed in the queue.
- Cap: a queue created with cap=5 over run 32 reported total=5, judged=1, remaining=4 and served exactly 5 rows (ids 100-104) — the cap, not the 130-row source size.
- Item payload vs `detections`: all 130 served rows matched their row on start_idx, end_idx, score (to 1e-12) and recording_id, with zero mismatches; spot-checked first (id 100, 2380/2440) and last (id 629, 3490/3550).
- Item payload vs `sequences`: all 30 served rows of queue 1 matched start_idx/end_idx/recording_id; `channel` on the sequence row agreed with the recording's channel.
- Held-out READ routes refuse correctly: GET /queues/6/items/2 returns `refused` = 'M4_aug fs1 is held out (D6)...' with context/shape/thumb all empty, and the channels route returns []. No trace data leaks.

### Write-safety critic

- Detections queue verdict: POST /queues/2/verdict target 100 -> exactly one adjudications row (detection_id=100), ZERO new annotations rows, exactly one review_audit row (queue_id=2, target_table='adjudications', target_ids='[100]'). The primary check in item 1 passes.
- Rule 5, annotation -> adjudications direction, refused cleanly: target 11266 on queue 2 returned 409 with the core's verbatim message and the table diff was EMPTY — no adjudications row, no annotations row, no audit row. The refusal does not half-write.
- A batch containing a rule-5 crossing writes nothing at all: batch [115,116,11266] on queue 2 -> 409, and detections 115 and 116 have no adjudications row. write_batch's check-all-before-write-any is real.
- Full verdict vocabulary: seed/interesting/not_interesting/artifact/unsure all land with the exact string, one adjudications row and one audit row each. 'BOGUS' and 'SEED' both 400 with the vocabulary listed, and the table diff was empty for both.
- Batch = one act: 5 targets -> one review_audit row action='batch' target_ids='[710,711,712,713,714]'; 130 targets (the whole queue) -> ONE audit row, adjudications 9->134, queue counts total 130 / judged 130 / remaining 0. One undo reversed all 130 exactly (adjudications back to 9).
- Undo restores rather than deletes: fresh verdict -> undo -> row gone (unjudged). verdict 'interesting/first' -> re-verdict 'artifact/second' -> undo -> row is back to 'interesting'/'first', not deleted. A second undo then removes it. A third walks on to the previous act. After the 130-row batch undo, detection 110's pre-existing 'seed' verdict was restored, not dropped.
- Undo with nothing to undo: on a freshly created queue with no audit rows, POST /undo returns 200 {'undone': null} and writes nothing.
- Undo is scoped per queue: POST /queues/1/undo reversed a queue-1 act and left the adjudications table byte-identical.
- Promotion idempotence: promote detection 110 -> one motif_entry (3610), one motif_member (3605), one motif_member_revision (origin='machine', detection_id=110, annotation_id=NULL), one adjudications row, one audit row action='promote'. Promoting the SAME target again -> created:false, zero new motif_entry/motif_member/motif_member_revision rows.
- Concurrency: 8 simultaneous verdict POSTs on distinct targets all returned 200, produced exactly 8 adjudications rows and 8 distinct review_audit rows. Nothing was lost or interleaved.
- Adversarial inputs are all refused with no write: target 999999 and -1 -> 400 'no detection with id ...'; queue 9999 and 'abc' -> 404; missing/null verdict and missing/null target_id -> 422; target_id '100 OR 1=1' -> 400 (parameterised, no injection). Table diff across the whole adversarial sweep showed only the two writes that were supposed to succeed.
- review_queues.writes_to CHECK constraint holds: writes_to='detections' and 'sequences' are both rejected at the database, so a queue cannot claim to write the detections table.

## What no critic could test, and why

### Function critic

- Checklist 2 (inspector panes paint: context trace, shape, nearest families, pills) — blocked by P0-1; nothing paints at all.
- Checklist 3 (S/I/N/A/U write the verdict the key means; Space skips without writing; Ctrl-Z undoes; auto-advance) — blocked by P0-1/P0-2. I pressed s, i and Space and nothing happened, so I cannot say whether the mapping is right, only that it is unreachable.
- Checklist 4 (progress and pace update as you judge) — blocked; no progress element ever rendered.
- Checklist 6 (cluster page renders a real grouping; accept/reject) — blocked twice over: #/review/cluster/1 hits the same render crash, AND GET /api/review/queues/2 returns "clusters": [], so there is no real grouping to render even once the crash is fixed. The report's own §6 notes clusterQueue() is still a synchronous fixture read, which is why the /#/review/cluster/<n> alias cannot resolve to a live queue.
- Whether §9.2 (a rediscovery asked twice) is now fixed end-to-end in the UI — the bridge does emit prior_verdict/prior_iou/prior_onset_gap on queue-2 rows (all null on this data), but I could not see whether the inspector surfaces them.
- Whether the extract-events span-edit flow (POST .../extract) works — unreachable through the UI.

### Data-truth critic

- Window queues (`training-windows` / `model-verification`) against real data — no `window_sets` rows with n_windows exist in this sandbox, so `window_verdicts` counts could not be diffed against a real source. Another critic's 'CRITIC ws-empty' queue reports 0/0/0, which is all the data supports.
- Cluster counts (`clusters` in the queue payload) — neither seeded queue's items carry a cluster_no, so the list is legitimately empty and there was nothing to diff.
- `seed-search` and `explore-spans` queue kinds against real data — the sandbox has exactly one annotation with verdict='seed' (id 100, recording 6) and no seeded search sessions, so neither resolver could be exercised at a meaningful size.
- Whether the header/queue counts are correct in --project mode: everything here was measured against the sandbox copy only.

### Write-safety critic

- Cluster accept/reject and GET /cluster/{no} (brief item 7) — unreachable: neither seeded queue produces any cluster, because no resolver emits cluster_no/clusterNo (see the P2 finding). No verdict could be written through that path at all.
- Window-verdict writes (writes_to='window_verdicts') — there are no window_sets rows in this sandbox database, and _resolve_windows returns [] without one. The window branch of write_verdict, the target-id-IS-the-index rule and _restore_window are therefore untested here; report §9.3 already flags this branch as smoke-covered only.
- Undo of a TAGGED verdict — blocked by the tags 500. Reading _restore_adjudication/_restore_annotation suggests undo restores verdict and note but not tags, so a re-judge's undo would leave the newer tags behind; I could not demonstrate it.
- Promotion of a HUMAN span (origin='human', annotation_id set) — the only annotations-writing queue on this bridge is extract-events, whose target ids are sequence ids, so promote would resolve the wrong annotation for the reasons in the first P0. Only the machine path was exercised.
- True write-write contention on the SAME target from two processes — I ran 8 threads on 8 distinct targets. Note also that another critic session was writing to this same bridge during my run (review_audit rows 2, 3 and queue 3 are not mine), so absolute table counts in my transcript include their writes; every finding above is anchored on specific row ids I wrote, not on totals.
