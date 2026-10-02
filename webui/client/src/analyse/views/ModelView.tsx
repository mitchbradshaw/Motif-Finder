/* Model view (fixup-h). Minimum: ACCURACY PER CLASS AS BARS. The renderer used to say "a model has no natural
 * plot"; that is only true of the joblib. The holdout the classifier already takes has an accuracy per class,
 * and a single headline number hides exactly the case that matters — a rare class the model never gets right.
 * Thumbnail: a card (low priority by the researcher's own ranking). A model with no holdout says why, on the
 * face of the card: that absence is the result, not commentary. */
import type { ModelPayload } from '../../api'
import { Bars } from '../../kit'
import type { ViewCtx } from './common'

type Num = Record<string, number>

export function ModelView({ p, ctx }: { p: ModelPayload; ctx: ViewCtx }) {
  const c = p.card ?? {}
  const base = p.path.split(/[\\/]/).pop() ?? p.path
  const acc = typeof c.holdout_accuracy === 'number' ? (c.holdout_accuracy as number).toFixed(2) : '—'
  const hasCard = Object.keys(c).length > 0
  const params = Object.entries((c.params ?? {}) as Record<string, unknown>).map(([k, v]) => [k, String(v)] as const)
  const per = (c.per_class_accuracy ?? null) as Num | null
  const counts = (c.holdout_class_counts ?? {}) as Num
  const classes = per ? Object.keys(per).sort((a, b) => Number(a) - Number(b)) : []
  return (
    <div className="bp-model" style={{ padding: '6px 12px' }} data-render="model">
      <div><b>{base}</b> <span className="muted">· {p.exists ? `${((p.size_bytes ?? 0) / 1024).toFixed(0)} kB on disk` : 'file missing'}</span></div>
      {hasCard
        ? <>
            <div>holdout accuracy <b>{acc}</b> · classes {String(c.n_classes ?? '—')} · windows {String(c.n_windows ?? '—')} · features kept {String(c.n_features_kept ?? '—')} of {String(c.n_features_in ?? '—')} · train/holdout {String(c.n_train ?? '—')}/{String(c.n_holdout ?? '—')}</div>
            {acc === '—' && typeof c.holdout_reason === 'string' && <div className="muted" data-testid="model-holdout-reason">{c.holdout_reason}</div>}
            {!ctx.interactive && per && <div data-testid="model-per-class-line">per class · {classes.map(k => `${k}: ${per[k].toFixed(2)}`).join(' · ')}</div>}
            {params.length > 0 && <div className="muted mono" data-testid="model-params">{params.map(([k, v]) => `${k} ${v}`).join(' · ')}</div>}
          </>
        : <div className="muted" data-testid="model-no-meta">model metadata not served for this run · the card comes from the adapter's meta (kept in a sidecar since critique r1)</div>}
      {ctx.interactive && hasCard && (
        per && classes.length
          ? <div data-testid="model-per-class" style={{ marginTop: 8 }}>
              <Bars categories={classes.map(k => `class ${k} · n ${counts[k] ?? '?'}`)} series={[{ key: 'acc', label: 'holdout accuracy', colour: 'var(--blue)', values: classes.map(k => per[k]) }]}
                yMax={1} format={v => v.toFixed(2)} height={170} legend={false} />
              <div className="muted" style={{ fontSize: 10.5 }}>accuracy on the holdout windows of each class · weighted by the class counts these are the headline {acc}</div>
            </div>
          : <div className="callout warn" data-testid="model-no-per-class" style={{ marginTop: 8, padding: '6px 10px', background: '#fff7e6', borderRadius: 6 }}>
              no accuracy per class: {typeof c.holdout_reason === 'string' ? c.holdout_reason : 'this model was fitted with no holdout, or by a run from before the classifier reported it — re-run the stage'}
            </div>
      )}
    </div>
  )
}
