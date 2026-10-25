/* tq-scope (2026-10-25): the rule `useSourcedFor` (./seam.ts) applies to the read it holds, kept pure (no imports) so
 * tests/test_site_runs_scope_link.py runs it under Node. A held answer counts only for the key it was read for:
 * anything else is "not in yet" (data null) and loading — from the very render the key changes in, before the new
 * read's effect has run — unless the read failed, when the error is the answer. */

export interface HeldRead<T> { data: { key: string; value: T } | null; loading: boolean; error: Error | null }

export function heldFor<T>(held: HeldRead<T>, key: string): { data: T | null; loading: boolean } {
  const fresh = !!held.data && held.data.key === key
  return { data: fresh ? held.data!.value : null, loading: held.loading || (!fresh && !held.error) }
}
