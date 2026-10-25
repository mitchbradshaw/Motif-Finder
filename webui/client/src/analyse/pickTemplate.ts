/* night-b (critic round): which saved template a `?template=<value>` link means. Names are not unique and the
 * bridge lists builtin first, then by id, so "the first loose match" could be `foo · v1` for `foo`. The rule: an
 * exact full name first, then the short name (before " · "); several of either → the newest id, said in `note`;
 * an all-digit value that no name matches is an id. Pure, no imports: tests/test_webui_night_b_critic.py runs it
 * under Node. tq-analyse (2026-10-25): `shortName` lives here, and TemplatesPopover.tsx imports it (it used to keep
 * a copy, because this file was thought unable to share with a React one). */
export interface NamedTemplate { id: number | string; name: string }

/** A template's short name: its name before " · " (the import names the chain after it). */
export const shortName = (t: { name: string }) => t.name.split(' · ')[0].trim()

export function pickTemplate<T extends NamedTemplate>(list: T[], q: string): { template: T | null; note: string | null } {
  const newest = (xs: T[]) => xs.reduce((a, b) => (Number(b.id) > Number(a.id) ? b : a))
  for (const hits of [list.filter(t => t.name === q), list.filter(t => shortName(t) === q)]) {
    if (hits.length === 1) return { template: hits[0], note: null }
    if (hits.length > 1) {
      const t = newest(hits)
      return { template: t, note: `${hits.length} saved templates are called “${q}”; opened the newest (id ${t.id})` }
    }
  }
  if (/^\d+$/.test(q)) {
    const t = list.find(x => String(x.id) === q)
    if (t) return { template: t, note: null }
  }
  return { template: null, note: null }
}
