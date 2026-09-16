/* analyse.training.model — placeholder while the page is being built (replaced in the next commit). */
import { EmptyState, Page } from '../kit'
import { Header } from '../shell/Header'

export function ModelPage() {
  return (
    <>
      <Header workspace="Analyse" page="05 Model" subtitle="being built" />
      <Page testid="training-model">
        <EmptyState icon="hourglass" title="05 Model is being built" caption="the page lands in the next commit" />
      </Page>
    </>
  )
}
