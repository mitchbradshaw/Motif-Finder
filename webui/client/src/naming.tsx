/* THE naming seam (fixup-f). What a dataset is called is decided in exactly one place on each side of the
 * bridge: `Working.database.datasets.display_name` on the server, and this module in the client.
 *
 *   a dataset is printed by its display name when it has one, and by its source file when it does not;
 *   the source file is always reachable — on hover here, in provenance, in the audit trail — because it
 *   is what the files on disk are called and what every log line says.
 *
 * A page that holds a dataset's identifier (its `source_file`, or the directory stem Settings and Discovery
 * key by) prints it with `<DatasetName file=… />` or `datasetName(names, file)`. No page formats a file
 * name into a label itself — no `.replace(/\.mat$/, '')`, no `_concat` stripping. A display name is a
 * LABEL: nothing here returns it as a key, and nothing may key, filter, cache or route on it.
 *
 * The names come from one read (`GET /api/datasets`), shared by every page and re-read after Settings ›
 * Datasets saves. Until it lands — and for a name it has never heard of — the identifier itself is printed,
 * which is the rule's own fallback, not a second one. */
import { useSyncExternalStore } from 'react'
import { getDatasetNames, type DatasetIdentity } from './api'

export type DatasetNames = Record<string, DatasetIdentity>

let names: DatasetNames = {}
let started = false
const listeners = new Set<() => void>()

function index(list: DatasetIdentity[]): DatasetNames {
  const out: DatasetNames = {}
  /* the stem first, the file last: where a stem and a file collide the file wins */
  for (const d of list) out[d.stem] = d
  for (const d of list) out[d.source_file] = d
  return out
}

/** (Re)read the names. Called once on first use and again after a save on Settings › Datasets. */
export function refreshDatasetNames(): Promise<void> {
  started = true
  return getDatasetNames().then(r => { names = index(r.datasets); listeners.forEach(l => l()) },
    e => { console.error('read failed', e) })
}

function subscribe(l: () => void) {
  listeners.add(l)
  if (!started) void refreshDatasetNames()
  return () => { listeners.delete(l) }
}

/** Every dataset's identity, keyed by source file and by directory stem. Re-renders when the names change. */
export function useDatasetNames(): DatasetNames {
  return useSyncExternalStore(subscribe, () => names, () => names)
}

const base = (file: string) => file.split(/[\\/]/).pop() ?? file

/** The dataset behind an identifier (source file, path to it, or directory stem), if it is registered. */
export function datasetOf(all: DatasetNames, file: string | null | undefined): DatasetIdentity | null {
  if (!file) return null
  return all[file] ?? all[base(file)] ?? null
}

/** THE rule, client side: the display name, else the identifier as given. */
export function datasetName(all: DatasetNames, file: string | null | undefined): string {
  return datasetOf(all, file)?.name ?? file ?? ''
}

/** The hover text: the source file first (always), then what Settings › Datasets knows about it. */
export function datasetTitle(all: DatasetNames, file: string | null | undefined): string {
  const d = datasetOf(all, file)
  if (!d) return file ? `source file ${file}` : ''
  return [
    `source file ${d.source_file}`, d.species, d.organism_id ? `organism ${d.organism_id}` : null, d.experiment_date, d.condition,
    `${d.n_channels} ch`, `${Number.isInteger(d.fs) ? d.fs : d.fs.toFixed(2)} Hz`, `${d.duration_h >= 10 ? Math.round(d.duration_h) : d.duration_h.toFixed(1)} h`,
    d.named ? null : 'not named yet · Settings › Datasets',
  ].filter(Boolean).join(' · ')
}

/** A dataset, printed by name, with its source file one hover away. `file` is the identifier, never the label. */
export function DatasetName({ file, className, testid }: { file: string | null | undefined; className?: string; testid?: string }) {
  const all = useDatasetNames()
  const d = datasetOf(all, file)
  return (
    <span className={className} title={datasetTitle(all, file)} data-testid={testid} data-source-file={d?.source_file ?? file ?? undefined}
      data-named={d ? (d.named ? '1' : '0') : undefined}>{datasetName(all, file)}</span>
  )
}

/** `DatasetName` for a string context (a toast, an option label, a caption): the name only. */
export function useDatasetName(file: string | null | undefined): string {
  return datasetName(useDatasetNames(), file)
}
