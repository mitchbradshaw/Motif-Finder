/* Species, from a list (2026-10-13): a common name with the Latin name in brackets — oyster
   (Pleurotus ostreatus) — plus every species already used on another dataset, plus "other…" for one
   the list lacks. The stored value is still free text (`datasets.species TEXT`), so the list is a
   convenience, never a lock: a dataset saved under a name the list does not carry reads as "other"
   with its text beside it. */
import { useState } from 'react'
import { Dropdown, TextField, type MenuItem } from '../kit'

/** The species this project records, and the ones it is likely to meet (the researcher, 2026-10-13). */
export const SPECIES: string[] = [
  'oyster (Pleurotus ostreatus)',
  'reishi (Ganoderma lucidum)',
  "lion's mane (Hericium erinaceus)",
  'ghost fungus (Omphalotus nidiformis)',
  'enoki (Flammulina velutipes)',
  'split gill (Schizophyllum commune)',
  'caterpillar fungus (Cordyceps militaris)',
]
const OTHER = '__other__'

export function SpeciesField({ value, onChange, known, disabled, disabledReason }: {
  value: string; onChange: (v: string) => void; known: string[]; disabled?: boolean; disabledReason?: string
}) {
  const extra = known.filter(k => k && !SPECIES.includes(k))
  const listed = SPECIES.includes(value) || extra.includes(value)
  const [other, setOther] = useState(() => !!value && !listed)
  const options: MenuItem[] = [
    ...SPECIES.map(s => ({ value: s, label: s })),
    ...extra.map(s => ({ value: s, label: s, description: 'already used on another dataset' })),
    { value: OTHER, label: 'other…', description: 'type a species the list lacks' },
  ]
  const shown = other || (!!value && !listed) ? OTHER : value
  return (
    <>
      <Dropdown value={shown || null} placeholder="not set" options={options} block ariaLabel="species" testid="species"
        disabled={disabled} disabledReason={disabledReason}
        onChange={v => { if (v === OTHER) setOther(true); else { setOther(false); onChange(v) } }} />
      {(other || (!!value && !listed)) && (
        <TextField value={value} onChange={onChange} block placeholder="common name (Genus species)" testid="species-other"
          disabled={disabled} disabledReason={disabledReason} />
      )}
    </>
  )
}
