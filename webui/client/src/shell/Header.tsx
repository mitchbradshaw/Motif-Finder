/* Header (frame shell-header): "Explore | Corpus  bird's-eye across every channel" on the left;
   search pill, "N need you" and "M4 held out" chips on the right. A page that rendered any fixture
   read passes `demo` and gets the "demo data" chip (brief: fixture pages say so in the header). */
import type { ReactNode } from 'react'
import { DEMO_NEED_YOU } from '../fixtures/canon'
import { navigate, useApp } from '../state'
import { useNotWired } from '../kit/notWired'

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
  const total = needYou + DEMO_NEED_YOU
  return (
    <header className="hdr" data-testid="header">
      <div className="hdr-left">
        <span className="hdr-ws">{workspace}</span>
        <span className="divider-v" />
        <span className="hdr-page" data-testid="header-page">{page}</span>
        {subtitle && <span className="hdr-sub mono">{subtitle}</span>}
        {demo && <span className="chip demo" data-testid="demo-chip" title="parts of this page show fixture data from the spec §0 placeholder canon, not your database; writes stay in this browser tab until reload (live pages keep their live regions live)">demo data</span>}
      </div>
      <div className="hdr-right">
        {extra}
        <button className="hdr-search mono" data-testid="header-search" title={onSearch ? search : 'global search is not wired yet'}
          onClick={() => (onSearch ? onSearch() : notWired(`global search (${search.toLowerCase()})`))}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
          <span>{search}</span><kbd>{searchHint}</kbd>
        </button>
        {bridgeDown && <span className="chip red" title="the FastAPI bridge did not answer the last poll; retrying every 5 s">bridge unreachable</span>}
        <button className={`chip ${total ? 'blue' : 'grey'}`} data-testid="need-you" onClick={() => navigate('jobs')}
          title={`${DEMO_NEED_YOU} from demo fixtures (paused runs, a failed cluster job) · ${needYou} live: runs started from this tab that failed — opens Jobs`}>● {total} need you</button>
        <button className="chip grey" data-testid="held-out-chip" onClick={() => navigate('settings/datasets')} title="M4_aug_concat_fs1.mat is held out (D6): every workspace refuses it — opens Settings › Datasets">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg> M4 held out
        </button>
      </div>
      <style>{`
        .hdr { height: var(--header-h); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; background: var(--bg); border-bottom: 1px solid var(--border); flex: none; }
        .hdr-left { display: flex; align-items: center; gap: 12px; min-width: 0; }
        .hdr-ws { font-weight: 700; font-size: 15px; }
        .hdr-page { font-size: 13.5px; color: var(--text-2); }
        .hdr-sub { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .hdr-right { display: flex; align-items: center; gap: 8px; }
        .hdr-search { display: flex; align-items: center; gap: 8px; height: 28px; padding: 0 12px; border-radius: 999px; background: var(--card); border: 1px solid var(--border); color: var(--muted); font-size: 11.5px; min-width: 280px; cursor: text; }
        .hdr-search kbd { margin-left: auto; font-family: var(--font-mono); font-size: 10px; color: var(--muted-2); }
        button.chip { cursor: pointer; }
        .chip.demo { background: #fff; border: 1px dashed var(--amber); color: #a05e00; height: 22px; font-size: 10.5px; }
      `}</style>
    </header>
  )
}
