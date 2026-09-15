/* The empty Motifs section (frame library-5, left column): the two ways in. A data condition of every Motifs
 * route (`?library=empty`, sticky for the session), never a blank grid. */
import { Button, Icon, Page } from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { SectionBar } from './chrome'

export function EmptyLibraryCard({ highlightImport, onImport }: { highlightImport?: boolean; onImport?: () => void }) {
  return (
    <>
      <div className="k-card lib-empty-card" data-testid="library-empty">
        <div className="lib-empty-icon"><Icon name="library" size={26} /></div>
        <h2 style={{ margin: '4px 0 0', fontSize: 20, fontWeight: 700 }}>The motif library is empty</h2>
        <div className="lib-cap" style={{ fontSize: 11 }}>No families, no exemplars yet. Two ways in:</div>
        <div className="lib-way" data-testid="way-review">
          <span style={{ color: 'var(--blue)' }}><Icon name="checklist" size={16} /></span>
          <div className="stack" style={{ gap: 4 }}>
            <span className="t">Judge candidates in Review</span>
            <span className="lib-cap">pressing S on a candidate creates an exemplar here</span>
            <div><Button icon={undefined} iconRight="arrow-right" testid="open-review" onClick={() => navigate('review/queue/q-12')}>Open Review</Button></div>
          </div>
        </div>
        <div className={`lib-way${highlightImport ? ' on' : ''}`} data-testid="way-import">
          <span style={{ color: 'var(--blue)' }}><Icon name="download" size={16} /></span>
          <div className="stack" style={{ gap: 4 }}>
            <span className="t">Import motifs you have already extracted</span>
            <span className="lib-cap">a bundle with provenance; safe to run twice</span>
            <div><Button variant="primary" icon="download" testid="import-open" onClick={() => (onImport ? onImport() : navigate('library/import?library=empty'))}>Import…</Button></div>
          </div>
        </div>
      </div>
      <div className="k-card" style={{ padding: '14px 18px' }} data-testid="groupings-placeholder">
        <div style={{ color: 'var(--muted)', fontSize: 13 }}>Groupings appear once there is something to group</div>
        <div className="lib-cap" style={{ marginTop: 6 }}>single motifs · sequences · spike trains, by distance, feature bins or labels</div>
      </div>
    </>
  )
}

/** Full-width empty Motifs page (recurrence / atlas / family routes when the catalogue holds 0 motifs). */
export function EmptyMotifsPage() {
  return (
    <>
      <Header workspace="Library" page="Motifs" subtitle="empty" search="Search spans, runs, families" demo />
      <Page>
        <SectionBar section="motifs" actions={<Button variant="primary" icon="download" testid="library-import" onClick={() => navigate('library/import?library=empty')}>Import</Button>} />
        <div style={{ maxWidth: 600, width: '100%', margin: '24px auto 0', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <EmptyLibraryCard />
        </div>
      </Page>
    </>
  )
}
