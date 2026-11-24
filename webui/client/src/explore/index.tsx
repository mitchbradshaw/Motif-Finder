/* Explore workspace entry — routes #/explore/corpus, #/explore/signal/<channelId>,
   #/explore/cross-channel/<channelId>, #/explore/span-edit/<spanId> and #/explore/autodetect/<channelId>. */
import { useApp } from '../state'
import { AutoDetectPage } from './AutoDetectPage'
import { CorpusPage } from './CorpusPage'
import { CrossChannelPage } from './CrossChannelPage'
import { SignalPage } from './SignalPage'
import { SpanEditPage } from './SpanEditPage'
import './explore.css'

export function ExplorePage() {
  const { route } = useApp()
  if (route.page === 'signal') return <SignalPage key={route.params.id ?? ''} channelId={Number(route.params.id)} />
  if (route.page === 'cross-channel') return <CrossChannelPage key={route.params.id ?? ''} channelId={Number(route.params.id ?? 4)} />
  if (route.page === 'span-edit') return <SpanEditPage key={route.params.id ?? ''} memberId={route.params.id ?? ''} />
  if (route.page === 'autodetect') return <AutoDetectPage key={route.params.id ?? ''} channelId={Number(route.params.id)} />
  return <CorpusPage />
}
