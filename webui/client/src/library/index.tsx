/* Library workspace entry — owned by the Library builder. Three sections (P22): Motifs (recurrence → atlas →
 * family, grouping, import) · Window sets · Templates. Every page reads fixtures through api/library.ts. */
import './library.css'
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

export function LibraryPage() {
  const { route } = useApp()
  const page = route.parts[0] || 'recurrence'
  switch (page) {
    case 'atlas': return <AtlasPage />
    case 'family': return <FamilyPage />
    case 'recurrence': return <RecurrencePage />
    case 'grouping': return <GroupingPage />
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
