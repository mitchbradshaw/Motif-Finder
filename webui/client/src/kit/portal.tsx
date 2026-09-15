/* Where floating surfaces mount. By default document.body; inside a Modal the dialog element is the host, so a
 * popover opened from a modal stays inside the modal's DOM (its outside-click and Tab trap keep working). */
import { createContext, useContext, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export const PortalHostContext = createContext<HTMLElement | null>(null)

export function Portal({ children }: { children: ReactNode }) {
  const host = useContext(PortalHostContext)
  if (typeof document === 'undefined') return null
  return createPortal(children, host ?? document.body)
}

export interface TestIdProps { testid?: string; 'data-testid'?: string }
export const tid = (p: TestIdProps) => p['data-testid'] ?? p.testid

export const cx = (...xs: (string | false | null | undefined | 0)[]) => xs.filter(Boolean).join(' ')
