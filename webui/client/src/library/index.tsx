/* Library workspace entry — owned by the Library builder. Three sections (P22): Motifs (recurrence → atlas →
 * family, grouping, import) · Window sets · Templates. Every page reads fixtures through api/library.ts. */
import './library.css'
import { useEffect } from 'react'
import { navigate, useApp } from '../state'
import { Button, EmptyState, Page } from '../kit'
import { Header } from '../shell/Header'
import { AtlasPage } from './AtlasPage'
import { FamilyPage } from './FamilyPage'
import { RecurrencePage } from './RecurrencePage'
import { GroupingPage } from './GroupingPage'
import { ImportPage } from './ImportPage'
import { WindowSetsPage } from './WindowSetsPage'
import { TemplatesPage } from './TemplatesPage'
import { GroupingGate } from './chrome'

function SequencesRedirect() {
  const { route } = useApp()
  const q = Object.entries({ ...route.query, unit: 'sequences' }).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
  useEffect(() => { window.location.replace(`#/library/atlas?${q}`) }, [q])
  return null
}

export function LibraryPage() {
  const { route } = useApp()
  const page = route.parts[0] || 'recurrence'
  switch (page) {
    // the four pages that read "the current grouping" sit behind the gate that answers for `?grouping=`
    case 'atlas': return <GroupingGate><AtlasPage /></GroupingGate>
    case 'family': return <GroupingGate><FamilyPage /></GroupingGate>
    case 'recurrence': return <GroupingGate><RecurrencePage /></GroupingGate>
    case 'grouping': return <GroupingGate editor><GroupingPage /></GroupingGate>
    // `library/sequences` is the atlas at `unit=sequences` (prompt `sequences`): the URL is replaced, not pushed,
    // so Back does not bounce through it
    case 'sequences': return <SequencesRedirect />
    case 'import': return <ImportPage />
    case 'window-sets': return <WindowSetsPage />
    case 'templates': return <TemplatesPage />
    default: return (
      <>
        <Header workspace="Library" page="Not found" subtitle={`#/library/${page}`} />
        <Page><EmptyState icon="alert-triangle" bordered testid="library-unknown-page" title={`No Library page called “${page}”`} caption="the Library has Motifs (recurrence, atlas, family, grouping, import), Window sets and Templates"
          action={<Button onClick={() => navigate('library/recurrence')}>Open Recurrence</Button>} /></Page>
      </>
    )
  }
}
