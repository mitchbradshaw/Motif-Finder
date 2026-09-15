/* Explore workspace entry — routes #/explore/corpus, #/explore/signal/<channelId>,
   #/explore/cross-channel/<channelId> and #/explore/span-edit/<spanId>. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'
import { CorpusPage } from './CorpusPage'
import { SignalPage } from './SignalPage'
import './explore.css'

export function ExplorePage() {
  const { route } = useApp()
  if (route.page === 'signal') return <SignalPage key={route.params.id ?? ''} channelId={Number(route.params.id)} />
  if (route.page === 'cross-channel') return <Skeleton id="explore.cross-channel" />
  if (route.page === 'span-edit') return <Skeleton id="explore.span-edit" />
  return <CorpusPage />
}
