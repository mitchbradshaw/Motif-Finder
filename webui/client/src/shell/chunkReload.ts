/* ux-1019 (site-fixes item 1): a page left open across a rebuild must not die. Every workspace is a lazy chunk with a
   content hash in its name (assets/models-XXXX.js); a rebuild deletes the old names, so the next workspace the open
   page asks for answers 404 and React.lazy caches that rejection for good — "Try again" on the red card failed the
   same way. The cure is the page the server now serves: reload ONCE. A sessionStorage flag stops a loop: a chunk
   that still fails after the reload is a real fault and reaches the error card as before (loud, never blank); the
   flag is cleared as soon as any chunk loads. Vite's own preload failure (`vite:preloadError`) takes the same road. */
import { lazy, type ComponentType } from 'react'

const FLAG = 'ub:reloaded-for-chunk'
const STALE_CHUNK = /dynamically imported module|Failed to fetch|Importing a module script failed/

const readFlag = () => { try { return sessionStorage.getItem(FLAG) !== null } catch { return false } }
const setFlag = () => { try { sessionStorage.setItem(FLAG, String(Date.now())); return true } catch { return false } }
const clearFlag = () => { try { sessionStorage.removeItem(FLAG) } catch { /* storage blocked: nothing to clear */ } }

/** True when this error is a stale chunk and the page is reloading for it (once per session flag). */
function reloadOnceFor(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err)
  if (!STALE_CHUNK.test(msg) || readFlag() || !setFlag()) return false
  console.warn('[chunk] a module of the old build is gone (the client was rebuilt) — reloading once', msg)
  window.location.reload()
  return true
}

/** `import()` with the reload-once cure: resolves as before, clears the flag on success; on a stale chunk the page
 *  reloads and the promise never settles (Suspense keeps its loading card until the new page replaces it). */
export function loadChunk<M>(load: () => Promise<M>): Promise<M> {
  return load().then(
    m => { clearFlag(); return m },
    err => reloadOnceFor(err) ? new Promise<M>(() => {}) : Promise.reject(err),
  )
}

/** A named export of a lazily loaded module as a lazy component, through `loadChunk`. */
export const lazyNamed = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) =>
  lazy(() => loadChunk(load).then(m => ({ default: m[name] })))

/** Vite's preload helper fires `vite:preloadError` when a dependency chunk of a dynamic import 404s; preventing it
 *  stops the throw only when the page is actually reloading. Install once, at the shell. */
export function installChunkReload(): void {
  window.addEventListener('vite:preloadError', (ev: Event) => {
    // every preload failure is a missing file of the old build (a CSS one says "Unable to preload CSS"), so it is
    // named as one here rather than matched on its wording
    const p = (ev as Event & { payload?: unknown }).payload
    const msg = p instanceof Error ? p.message : String(p ?? '')
    if (reloadOnceFor(new Error(`Failed to fetch dynamically imported module (vite:preloadError) ${msg}`))) ev.preventDefault()
  })
}
