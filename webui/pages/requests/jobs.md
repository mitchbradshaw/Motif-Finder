# Jobs — requests for shared code (kit / shell / fixtures / canon)

Everything here is worked around inside `webui/client/src/jobs/` so the build is never blocked.
Each entry: what · where · why · what I did instead.

## kit

1. **`Table` cannot deep-link its collapsed groups.** · `kit/Table.tsx` (`collapsibleGroups`) · frame jobs-1
   opens with **Finished and cancelled today** collapsed, and the state has to be reachable by
   `?finished=1` as well as by clicking. `Table` keeps `collapsed` in its own `useState`, so neither the
   default-collapsed group nor the URL round-trip is expressible. · **Worked around:** `jobs/AllPage.tsx`
   renders its own `<table class="jb-table">` with the group bars. A `defaultCollapsed?: string[]` plus
   `collapsed?/onCollapsedChange?` on `TableProps` would let Jobs (and any other grouped table) use the kit one.

2. **`Stepper` has no "stored"/"cached" step state.** · `kit/display.tsx` `StepState` = done | current |
   running | todo | failed | paused · a paused run's stage N is neither *done* (it did not run here) nor
   *todo*: its artifact was placed by hand. · **Worked around:** the run page draws its own stage cards
   (`.jb-stage`) rather than a `Stepper`, and uses `Badge status="cached"` for the stored stage. A
   `'cached'` member of `StepState` would cover it.

3. **`Modal` puts `subtitle` on the title line.** · `kit/surfaces.tsx` · frame jobs-3's subtitle
   (`r-0431 · Discovery run mp_drops_v3 · stage 3 of 4 · Matrix profile on M2_aug fs1 CH2_A1–CH4_A2`) is a
   full second line under the title; inline it truncates at `lg`. · **Worked around:** left truncating (the
   full text is in the `title` attribute). A `subtitleBelow` flag, or wrapping the subtitle when it exceeds
   the free space, would fix it for every long-subtitle modal.

4. **No progress-in-a-table-cell size for `ProgressBar`.** Minor: `size="sm"` plus `labelPosition="none"`
   works, but every consumer then re-adds the "62 %" label by hand (frame jobs-1 has it four times, and
   Models/Discovery draw the same pattern). A `suffix`/`percent` prop would remove the duplication.

## fixtures/canon.ts  (owner: the canon holder — I did not edit it)

5. **`CanonJob.status` has no `'submitted'`.** · `type CanonJob['status'] = 'finished' | 'running' | 'paused'
   | 'failed' | 'queue'` · §7c.4's hand-marked chain is script created → **submitted** → running → finished,
   and frame jobs-4 draws `submitted` as a completed pill. · **Worked around:** `fixtures/jobs.ts` declares
   its own `ClusterStatus` that adds `'submitted'` and `'cancelled'`. Adding both to `CanonJob` would let the
   two agree.

6. **`REVIEW_QUEUES` carries no counts, pace or ETA**, but frame jobs-1 prints "942 left of 1,284 · ~1.9 s
   each · 27 % · ~30 min" for q-12 and equivalents for q-15/q-18/q-19; only q-19 has `left`/`total`. The
   Review inventory asks for the same extension. · **Worked around:** `fixtures/jobs.ts` `QUEUE_JOBS` holds
   left/total/pace/eta/blind/idle. Two workspaces now own the same numbers; they belong in canon.

7. **`DEMO_NEED_YOU` / `DEMO_JOBS_ACTIVE` are constants that the Jobs page re-derives.** Both are 3 today.
   A shared helper (`demoNeedYou(jobs)`) in canon, used by `shell/Header.tsx` and by Jobs, would keep the
   header chip and the page from drifting once a demo write adds a fourth item. · **Worked around:** the page
   computes its own count and uses `DEMO_JOBS_ACTIVE` only as the header-subtitle fallback while loading.

8. **`j-0209`'s canon title is just `"j-0209"`.** Frame jobs-1 draws it as `matrix profile · M3_jul CH1–CH8`
   / `for r-0402 · Discovery`. `r-0402` exists nowhere else in the canon. · **Worked around:** both strings
   live in `fixtures/jobs.ts`.

## shell

9. **Nothing else.** `shell/Header.tsx` took the workspace/page/subtitle/search/demo props Jobs needs, and
   `state.tsx`'s `parseHash().parts` already reads `run/<id>/upload` and `cluster/<id>` without change.
