/* The kit barrel: `import { Page, SectionCard, Table, Trace, useQueryState } from '../kit'`. Importing it loads kit.css. */
import './kit.css'

export * from './layout'
export * from './nav'
export * from './surfaces'
export * from './display'
export * from './forms'
export { Table, type Column, type SortState, type TableProps } from './Table'
export * from './ChainRibbon'
export * from './glyphs'
export * from './plots'
export * from './icons'
export {
  useQueryState, useQueryFlag, usePagedList, copyToClipboard, fmtInt, fmtMv, fmtPct, useControllable, sampleIndices,
  useAnchoredPosition, useLayer, type PagedList, type Placement,
} from './hooks'
export { Portal, cx } from './portal'

/* orchestrator-provided runtime helpers, re-exported so pages have one import */
export { useDemoState, recordDemoWrite, useDemoWrites, getDemo, setDemo, type DemoWrite } from './store'
export { useSim, startSim, cancelSim, resetSim, forceSim, getSim, type SimStatus, type SimOptions, type SimState } from './sim'
export { useNotWired } from './notWired'
export { KitGallery } from './Gallery'
