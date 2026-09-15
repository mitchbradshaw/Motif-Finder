/* Settings entry — owned by the Settings builder. Routes: settings/<slug>. */
import { useApp } from '../state'
import { pageById } from '../shell/pages'
import { Skeleton } from '../shell/Skeleton'

export function SettingsPage() {
  const { route } = useApp()
  const id = `settings.${route.parts[0] || 'datasets'}`
  return <Skeleton id={pageById(id) ? id : 'settings.datasets'} />
}
