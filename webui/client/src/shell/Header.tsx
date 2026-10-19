/* Header (frame shell-header): "Explore | Corpus  bird's-eye across every channel" on the left;
   search pill, "N need you" and the held-out chip ("M4 held out" grey while the lock is on, "M4 unlocked"
   amber while it is off — a2-p1) on the right. A page that rendered any fixture read passes `demo` and gets
   the "demo data" chip (brief: fixture pages say so in the header). */
import type { ReactNode } from 'react'
import { useSharedNeedYou } from './needYouShared'
import { navigate, useApp } from '../state'
import { useNotWired } from '../kit/notWired'
import { useHeldOutLock } from './heldOutLock'
import { PathStrip } from './PathStrip'

export interface HeaderSpec {
  workspace: string; page: string; subtitle?: string; search?: string; demo?: boolean; extra?: ReactNode
  /** A workspace that owns its own search surface passes a handler; without one the pill says it is not wired.
   *  Settings uses this for its per-page search popover (its builder's request R1). */
  onSearch?: () => void
  searchHint?: string
}

export function Header({ workspace, page, subtitle, search = 'Search spans, runs, families', demo = false, extra, onSearch, searchHint = 'Ctrl K' }: HeaderSpec) {
  const { needYou, bridgeDown } = useApp()
  const notWired = useNotWired()
  // a2-p1: the lock as the bridge enforces it (GET /api/held-out, read when this header mounts and on window
  // focus), and Settings › Datasets' saved lock the moment it is saved (its store.ts HELD_OUT_KEY_STORE, the same key)
  const heldOut = useHeldOutLock()
  const short = heldOut.recording.replace(/_.*/, '')
  // The Review queues' own count, read from the bridge. It used to be the
  // fixture constant 3 while /api/review/counts said 160 — the one number in the
  // chrome that is supposed to tell a researcher there is work waiting, and it
  // was decoration.
  // night-c: one shared read for every header (a page mounts its header twice; the route costs seconds at scale)
  const review = useSharedNeedYou()
  const total = needYou + review
  return (
    <header className="hdr" data-testid="header">
      <div className="hdr-left">
        <span className="hdr-ws">{workspace}</span>
        <span className="divider-v" />
        <span className="hdr-page" data-testid="header-page">{page}</span>
        {subtitle && <span className="hdr-sub mono">{subtitle}</span>}
        {demo && <span className="chip demo" data-testid="demo-chip" title="parts of this page show fixture data from the spec §0 placeholder canon, not your database; writes stay in this browser tab until reload (live pages keep their live regions live)">demo data</span>}
      </div>
      <PathStrip />
      <div className="hdr-right">
        {extra}
        <button className="hdr-search mono" data-testid="header-search" title={onSearch ? search : 'global search is not wired yet'}
          onClick={() => (onSearch ? onSearch() : notWired(`global search (${search.toLowerCase()})`))}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
          <span>{search}</span><kbd>{searchHint}</kbd>
        </button>
        {bridgeDown && <span className="chip red" title="the FastAPI bridge did not answer the last poll; retrying every 5 s">bridge unreachable</span>}
        <button className={`chip ${total ? 'blue' : 'grey'}`} data-testid="need-you" onClick={() => navigate('jobs?section=review')}
          title={`${review} unjudged across the open review queues · ${needYou} live: runs started from this tab that failed — opens Jobs`}>● {total} need you</button>
        <button className={`chip ${heldOut.on ? 'grey' : 'amber'}`} data-testid="held-out-chip" data-locked={heldOut.on ? '1' : '0'}
          onClick={() => navigate('settings/datasets')}
          title={(heldOut.on
            ? `${heldOut.recording} is held out (D6): every workspace refuses it — to use it, ${heldOut.unlock ?? "turn the lock off in Settings › Datasets (type the recording's name)"}`
            : `${heldOut.recording} is UNLOCKED: every workspace (Explore, Analyse, Discovery, Review, Library) can use it, so evaluation on it is no longer protected. Turn the lock back on in Settings › Datasets. RQ1's exam (iii) in Models keeps its own lock.`)
            + (heldOut.error ? ` · could not read the lock from the bridge (${heldOut.error}): showing the last state this tab knew` : '')}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><rect x="5" y="11" width="14" height="10" rx="2" />{heldOut.on ? <path d="M8 11V7a4 4 0 0 1 8 0v4" /> : <path d="M8 11V7a4 4 0 0 1 8 0" />}</svg>
          {heldOut.on ? `${short} held out` : `${short} unlocked`}
        </button>
      </div>
      <style>{`
        .hdr { height: var(--header-h); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; background: var(--bg); border-bottom: 1px solid var(--border); flex: none; }
        .hdr-left { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1 1 auto; }
        .hdr-ws { font-weight: 700; font-size: 15px; }
        .hdr-page { font-size: 13.5px; color: var(--text-2); }
        .hdr-sub { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .hdr-right { display: flex; align-items: center; gap: 8px; flex: none; }
        .hdr-search { display: flex; align-items: center; gap: 8px; height: 28px; padding: 0 12px; border-radius: 999px; background: var(--card); border: 1px solid var(--border); color: var(--muted); font-size: 11.5px; min-width: 280px; cursor: text; white-space: nowrap; }
        .hdr-search kbd { margin-left: auto; font-family: var(--font-mono); font-size: 10px; color: var(--muted-2); }
        button.chip { cursor: pointer; }
        @media (max-width: 1240px) {
          .hdr-search { min-width: 0; } .hdr-search > span { display: none; }
        }
        .chip.demo { background: #fff; border: 1px dashed var(--amber); color: #a05e00; height: 22px; font-size: 10.5px; }
      `}</style>
    </header>
  )
}
