/* Settings entry — owned by the Settings builder. Routes: #/settings/<slug> (spec §9, §12 P23).
 * Sixteen pages behind one shell: fourteen project pages (recorded with runs) and two personal ones. */
import { useEffect } from 'react'
import { Button, EmptyState, Page } from '../kit'
import { Header } from '../shell/Header'
import { navigate, useApp } from '../state'
import { PAGE_META } from '../api/settings'
import { DatasetsPage } from './DatasetsPage'
import { ChannelsEventsPage } from './ChannelsEventsPage'
import { VocabularyPage } from './VocabularyPage'
import { Skeleton } from '../shell/Skeleton'

export function SettingsPage() {
  const { route } = useApp()
  const slug = route.parts[0] || ''
  useEffect(() => { if (!slug) history.replaceState(null, '', '#/settings/datasets') }, [slug])
  if (!slug || slug === 'datasets') return <DatasetsPage />
  if (slug === 'channels-events') return <ChannelsEventsPage />
  if (slug === 'vocabulary') return <VocabularyPage />
  if (PAGE_META[slug]) return <Skeleton id={`settings.${slug}`} />
  return (
    <>
      <Header workspace="Settings" page="Not found" subtitle={`#/settings/${slug}`} />
      <Page>
        <EmptyState icon="alert-triangle" bordered testid="settings-unknown-page" title={`No settings page called “${slug}”`}
          caption="Settings has sixteen pages — Datasets is the first"
          action={<Button onClick={() => navigate('settings/datasets')}>Open Datasets</Button>} />
      </Page>
    </>
  )
}
