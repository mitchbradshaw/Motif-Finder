/* Settings entry — owned by the Settings builder. Routes: #/settings/<slug> (spec §9, §12 P23).
 * Sixteen pages behind one shell: fourteen project pages (recorded with runs) and two personal ones. */
import { useEffect } from 'react'
import { Button, EmptyState, Page } from '../kit'
import { Header } from '../shell/Header'
import { navigate, useApp } from '../state'
import { DatasetsPage } from './DatasetsPage'
import { ChannelsEventsPage } from './ChannelsEventsPage'
import { VocabularyPage } from './VocabularyPage'
import { NullsPage } from './NullsPage'
import { AnalysisDefaultsPage } from './AnalysisDefaultsPage'
import { BlocksPage } from './BlocksPage'
import { ComputeHpcPage } from './ComputeHpcPage'
import { ReviewQueuesPage } from './ReviewQueuesPage'
import { ModelsRegistrationPage } from './ModelsRegistrationPage'
import { LibraryGroupingsPage } from './LibraryGroupingsPage'
import { StoragePage } from './StoragePage'
import { ExportPage } from './ExportPage'
import { AuditLogPage } from './AuditLogPage'
import { AboutPage } from './AboutPage'
import { DisplayPage } from './DisplayPage'
import { KeyboardPage } from './KeyboardPage'

export function SettingsPage() {
  const { route } = useApp()
  const slug = route.parts[0] || ''
  useEffect(() => { if (!slug) history.replaceState(null, '', '#/settings/datasets') }, [slug])
  if (!slug || slug === 'datasets') return <DatasetsPage />
  if (slug === 'channels-events') return <ChannelsEventsPage />
  if (slug === 'vocabulary') return <VocabularyPage />
  if (slug === 'nulls') return <NullsPage />
  if (slug === 'analysis-defaults') return <AnalysisDefaultsPage />
  if (slug === 'compute-hpc') return <ComputeHpcPage />
  if (slug === 'blocks') return <BlocksPage />
  if (slug === 'review-queues') return <ReviewQueuesPage />
  if (slug === 'models-registration') return <ModelsRegistrationPage />
  if (slug === 'library-groupings') return <LibraryGroupingsPage />
  if (slug === 'storage-backups') return <StoragePage />
  if (slug === 'export') return <ExportPage />
  if (slug === 'audit-log') return <AuditLogPage />
  if (slug === 'about') return <AboutPage />
  if (slug === 'display') return <DisplayPage />
  if (slug === 'keyboard') return <KeyboardPage />
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
