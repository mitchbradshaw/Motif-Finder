/* The unit a page prints beside a channel's numbers (fixup-b).

   The bridge converts every channel to millivolts at one seam (`webui/server/corpus.py::display_channel`)
   from the unit the recording declares (`recordings.units`, Settings › Datasets). A recording that declares
   none is served as stored with `unit: null` — and a page must then say so, never print "mV": for two years
   stored VOLTS were printed as "mV" here, and every amplitude read 1000x too small.

   `undefined` is a payload that predates the field (fixtures, demo blocks): those claim mV and keep it. */

export type DisplayUnit = 'mV' | null

/** Beside an axis value: "mV", or "?" when the recording declares no unit. */
export const axisUnit = (u: DisplayUnit | undefined): string => (u === null ? '?' : 'mV')

/** In a sentence or a caption: "mV", or "unit undeclared". */
export const unitWords = (u: DisplayUnit | undefined): string => (u === null ? 'unit undeclared' : 'mV')

/** The one-line explanation an undeclared unit carries wherever it is drawn. */
export const UNDECLARED_NOTE = 'this recording declares no unit, so its numbers are shown as stored — declare it in Settings › Datasets'
