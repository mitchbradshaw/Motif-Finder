/* ChainRibbon: a horizontal strip of blocks with arrows between (models-1 template strip, discovery-1b thumbnails,
 * the block page ribbon). Each block is a button when onSelect is given. */
import type { ReactNode } from 'react'
import { Badge, type BadgeStatus } from './display'
import { BlockGlyph, SourceGlyph } from './glyphs'
import { Icon } from './icons'
import { cx, tid, type TestIdProps } from './portal'

export interface RibbonBlock {
  id: string; label: ReactNode
  /** Glyph alias or registry name (see GLYPH_ALIASES); 'source' draws the source waveform. */
  glyph?: string; index?: number; signature?: ReactNode; status?: BadgeStatus; disabled?: boolean; reason?: string
}
export interface ChainRibbonProps extends TestIdProps {
  blocks: RibbonBlock[]; current?: string | null; onSelect?: (id: string) => void
  /** tiles: glyph over label (models-1) · chips: number + label + badge + signature (block page) · thumbs: glyphs only (discovery list rows). */
  variant?: 'tiles' | 'chips' | 'thumbs'; trailing?: ReactNode; ariaLabel?: string
}
const pad2 = (n: number) => String(n).padStart(2, '0')

export function ChainRibbon({ blocks, current, onSelect, variant = 'tiles', trailing, ariaLabel = 'chain', ...t }: ChainRibbonProps) {
  return (
    <div className={cx('k-ribbon', variant)} role="list" aria-label={ariaLabel} data-testid={tid(t)}>
      {blocks.map((b, i) => {
        const glyph = b.glyph === 'source' ? <SourceGlyph width={variant === 'thumbs' ? 36 : 44} height={variant === 'thumbs' ? 21 : 26} />
          : b.glyph ? <BlockGlyph name={b.glyph} width={variant === 'thumbs' ? 36 : 44} height={variant === 'thumbs' ? 21 : 26} /> : null
        const on = current === b.id
        const content = variant === 'tiles' ? (
          <>
            <span className="thumb">{glyph}</span>
            <span className="lbl">{b.index != null && b.index > 0 && <span className="mono muted" style={{ fontSize: 10.5 }}>{pad2(b.index)}</span>}<span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.label}</span>{b.status && <Badge status={b.status} />}</span>
            {b.signature && <span className="sig">{b.signature}</span>}
          </>
        ) : variant === 'chips' ? (
          <>
            <span className="t">{b.index != null && <span className="num">{pad2(b.index)}</span>}<span className="nm">{b.label}</span>{b.status && <Badge status={b.status} />}</span>
            {b.signature && <span className="sig">{b.signature}</span>}
          </>
        ) : glyph
        const title = b.disabled ? b.reason : typeof b.label === 'string' ? `${b.label}${typeof b.signature === 'string' ? ` · ${b.signature}` : ''}` : undefined
        return (
          <div key={b.id} role="listitem" style={{ display: 'contents' }}>
            {i > 0 && <span className="arrow" aria-hidden><Icon name="chevron-right" size={variant === 'thumbs' ? 11 : 13} /></span>}
            {onSelect
              ? <button type="button" className={cx('k-ribbon-block', on && 'on', b.status && `st-${b.status}`)} onClick={() => onSelect(b.id)} disabled={b.disabled} title={title} aria-current={on ? 'step' : undefined} data-testid={`ribbon-block-${b.id}`}>{content}</button>
              : <div className={cx('k-ribbon-block', on && 'on', b.status && `st-${b.status}`)} title={title} aria-current={on ? 'step' : undefined} data-testid={`ribbon-block-${b.id}`}>{content}</div>}
          </div>
        )
      })}
      {trailing}
    </div>
  )
}
