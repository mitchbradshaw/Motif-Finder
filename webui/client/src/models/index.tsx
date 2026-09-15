/* Models workspace entry — owned by the Models builder. Routes: launch, results, compare, registry (spec §7b, P14). */
import './models.css'
import { useEffect } from 'react'
import { navigate, useApp } from '../state'
import { Button, EmptyState, Page } from '../kit'
import { Header } from '../shell/Header'
import { LaunchPage } from './LaunchPage'
import { ResultsPage } from './ResultsPage'
import { ComparePage } from './ComparePage'
import { RegistryPage } from './RegistryPage'

export function ModelsPage() {
  const { route } = useApp()
  const page = route.parts[0] || ''
  useEffect(() => { if (!page) history.replaceState(null, '', '#/models/launch') }, [page])
  switch (page) {
    case '':
    case 'launch': return <LaunchPage />
    case 'results': return <ResultsPage />
    case 'compare': return <ComparePage />
    case 'registry': return <RegistryPage />
    default: return (
      <>
        <Header workspace="Models" page="Not found" subtitle={`#/models/${page}`} />
        <Page><EmptyState icon="alert-triangle" bordered testid="models-unknown-page" title={`No Models page called “${page}”`} caption="Models has four tabs: Launch, Results, Compare and Registry"
          action={<Button onClick={() => navigate('models/launch')}>Open Launch</Button>} /></Page>
      </>
    )
  }
}
