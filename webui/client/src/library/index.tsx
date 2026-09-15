/* Library workspace entry — owned by the Library builder. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'

const IDS: Record<string, string> = { recurrence: 'library.recurrence', atlas: 'library.atlas', family: 'library.family', grouping: 'library.grouping', import: 'library.import', 'window-sets': 'library.window-sets', templates: 'library.templates' }

export function LibraryPage() {
  const { route } = useApp()
  return <Skeleton id={IDS[route.parts[0]] ?? 'library.atlas'} />
}
