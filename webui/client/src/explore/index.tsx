/* Explore workspace entry — routes #/explore/corpus, #/explore/signal/<channelId>,
   #/explore/cross-channel/<channelId> and #/explore/span-edit/<spanId>. */
import { useApp } from '../state'
import { CorpusPage } from './CorpusPage'
import { CrossChannelPage } from './CrossChannelPage'
import { SignalPage } from './SignalPage'
import { SpanEditPage } from './SpanEditPage'
import './explore.css'

export function ExplorePage() {
  const { route } = useApp()
  if (route.page === 'signal') return <SignalPage key={route.params.id ?? ''} channelId={Number(route.params.id)} />
  if (route.page === 'cross-channel') return <CrossChannelPage key={route.params.id ?? ''} channelId={Number(route.params.id ?? 4)} />
  if (route.page === 'span-edit') return <SpanEditPage key={route.params.id ?? ''} memberId={route.params.id ?? 'm-1846'} />
  return <CorpusPage />
}
