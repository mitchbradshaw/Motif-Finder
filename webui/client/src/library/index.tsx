/* Library workspace entry — owned by the Library builder. Three sections (P22): Motifs (recurrence → atlas →
 * family, grouping, import) · Window sets · Templates. Every page reads fixtures through api/library.ts. */
import './library.css'
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'
import { AtlasPage } from './AtlasPage'
import { FamilyPage } from './FamilyPage'
import { RecurrencePage } from './RecurrencePage'

const IDS: Record<string, string> = { recurrence: 'library.recurrence', atlas: 'library.atlas', family: 'library.family', grouping: 'library.grouping', import: 'library.import', 'window-sets': 'library.window-sets', templates: 'library.templates' }

export function LibraryPage() {
  const { route } = useApp()
  const page = route.parts[0] ?? 'recurrence'
  switch (page) {
    case 'atlas': return <AtlasPage />
    case 'family': return <FamilyPage />
    case 'recurrence': return <RecurrencePage />
    default: return <Skeleton id={IDS[page] ?? 'library.atlas'} />
  }
}
