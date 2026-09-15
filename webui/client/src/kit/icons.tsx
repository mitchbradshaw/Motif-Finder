/* Line icons (the frames use a thin 1.6 px stroke set on a 24 px grid). No icon dependency: each icon is a
 * few SVG paths. `<Icon name="upload" />` renders at 14 px in currentColor. Unknown names render a small
 * dot and warn once in the console, so a typo is visible rather than silently blank. */
import type { CSSProperties, ReactElement } from 'react'

const P = (d: string) => <path d={d} />

export const ICONS = {
  search: <g><circle cx="11" cy="11" r="7" />{P('M20 20l-3.5-3.5')}</g>,
  info: <g><circle cx="12" cy="12" r="9" />{P('M12 11v5M12 7.6v.2')}</g>,
  x: P('M6 6l12 12M18 6L6 18'),
  check: P('M5 12.5l4.5 4.5L19 7.5'),
  'check-circle': <g><circle cx="12" cy="12" r="9" />{P('M8 12.3l2.8 2.8L16.2 9.5')}</g>,
  'x-circle': <g><circle cx="12" cy="12" r="9" />{P('M9 9l6 6M15 9l-6 6')}</g>,
  'alert-triangle': <g>{P('M12 4L2.8 19.5h18.4z')}{P('M12 10v4.5M12 17v.2')}</g>,
  'alert-circle': <g><circle cx="12" cy="12" r="9" />{P('M12 7.5v5.5M12 16.2v.2')}</g>,
  help: <g><circle cx="12" cy="12" r="9" />{P('M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.8M12 17v.2')}</g>,
  'circle-dashed': <circle cx="12" cy="12" r="8.5" strokeDasharray="2.6 2.6" />,
  hourglass: P('M7 3.5h10M7 20.5h10M8 3.5c0 4.5 8 5.5 8 8.5s-8 4-8 8.5M16 3.5c0 4.5-8 5.5-8 8.5s8 4 8 8.5'),
  clock: <g><circle cx="12" cy="12" r="9" />{P('M12 7v5l3 2')}</g>,
  'chevron-down': P('M6 9l6 6 6-6'),
  'chevron-up': P('M6 15l6-6 6 6'),
  'chevron-left': P('M15 6l-6 6 6 6'),
  'chevron-right': P('M9 6l6 6-6 6'),
  'arrow-right': P('M4.5 12h15M13.5 6l6 6-6 6'),
  'arrow-left': P('M19.5 12h-15M10.5 6l-6 6 6 6'),
  'arrow-down': P('M12 4.5v15M6 13.5l6 6 6-6'),
  'arrow-up': P('M12 19.5v-15M6 10.5l6-6 6 6'),
  external: P('M7 17L17 7M9 7h8v8'),
  plus: P('M12 5v14M5 12h14'),
  minus: P('M5 12h14'),
  upload: P('M12 15V4M7.5 8.5L12 4l4.5 4.5M4 15v4.5h16V15'),
  download: P('M12 4v11M7.5 10.5L12 15l4.5-4.5M4 15v4.5h16V15'),
  copy: <g><rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2" />{P('M15.5 8.5V5.5a1.5 1.5 0 0 0-1.5-1.5H5.5A1.5 1.5 0 0 0 4 5.5V14a1.5 1.5 0 0 0 1.5 1.5h3')}</g>,
  file: <g>{P('M6 3.5h8l4 4v13H6z')}{P('M14 3.5v4h4M9 12.5h6M9 16h6')}</g>,
  folder: P('M3.5 6.5a1.5 1.5 0 0 1 1.5-1.5h4.5l2 2.5h7.5a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 1-1.5 1.5H5a1.5 1.5 0 0 1-1.5-1.5z'),
  save: <g>{P('M5 4h11l3 3v13H5z')}{P('M8 4v5h7V4M8 20v-6h8v6')}</g>,
  play: P('M8 5.5v13l10.5-6.5z'),
  pause: P('M8.5 5v14M15.5 5v14'),
  stop: <rect x="6" y="6" width="12" height="12" rx="1.5" />,
  refresh: P('M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4h-4'),
  undo: P('M9 14L4.5 9.5 9 5M4.5 9.5h10a5 5 0 0 1 0 10H11'),
  lock: <g><rect x="5" y="11" width="14" height="9.5" rx="2" />{P('M8 11V7.5a4 4 0 0 1 8 0V11')}</g>,
  eye: <g>{P('M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z')}<circle cx="12" cy="12" r="3" /></g>,
  'eye-off': <g>{P('M4 4l16 16M10 5.7A9.8 9.8 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 0 1-2.6 3.3M6.3 7.2A15.6 15.6 0 0 0 2.5 12S6 18.5 12 18.5a9.6 9.6 0 0 0 4.3-1')}</g>,
  filter: P('M4 5h16l-6 7.5V19l-4-2v-4.5z'),
  sliders: P('M4 7h9M17 7h3M4 17h3M11 17h9M15 4.5v5M9 14.5v5'),
  settings: <g><circle cx="12" cy="12" r="3" />{P('M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8')}</g>,
  database: <g><ellipse cx="12" cy="6" rx="7.5" ry="2.8" />{P('M4.5 6v12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8V6M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8')}</g>,
  server: <g><rect x="4" y="4.5" width="16" height="6.5" rx="1.5" /><rect x="4" y="13" width="16" height="6.5" rx="1.5" />{P('M7.5 7.8h.2M7.5 16.2h.2')}</g>,
  cpu: <g><rect x="6.5" y="6.5" width="11" height="11" rx="1.5" /><rect x="9.5" y="9.5" width="5" height="5" />{P('M9.5 3.5v3M14.5 3.5v3M9.5 17.5v3M14.5 17.5v3M3.5 9.5h3M3.5 14.5h3M17.5 9.5h3M17.5 14.5h3')}</g>,
  rocket: P('M13.5 17.5l-7-7C9 5 13.5 3.5 20.5 3.5c0 7-1.5 11.5-7 14zM9 12.5L5 13l-1.5 3 3.5-.5M11.5 15l-.5 4 3-1.5.5-3.5M15 9h.2'),
  'bar-chart': P('M4 20h16M7 16.5V11M12 16.5V6.5M17 16.5v-4'),
  compare: P('M7 4v10M7 14l-3-3M7 14l3-3M17 20V10M17 10l-3 3M17 10l3 3'),
  library: <g><rect x="4" y="4" width="4" height="16" rx="1" /><rect x="10" y="4" width="4" height="16" rx="1" />{P('M16.5 5l3.5 14.5')}</g>,
  inbox: P('M3.5 13.5l2.5-8h12l2.5 8v5h-17zM3.5 13.5h5l1 2.5h5l1-2.5h5'),
  mail: <g><rect x="3.5" y="5.5" width="17" height="13" rx="2" />{P('M4 7l8 6 8-6')}</g>,
  tag: <g>{P('M3.5 12.5V4h8.5l8.5 8.5-8.5 8.5z')}<circle cx="8" cy="8.5" r="1.2" /></g>,
  layers: P('M12 4l8.5 4.5L12 13 3.5 8.5zM3.5 12.5L12 17l8.5-4.5M3.5 16.5L12 21l8.5-4.5'),
  trash: P('M4.5 6.5h15M9.5 6.5V4h5v2.5M6.5 6.5l1 13.5h9l1-13.5M10 10.5v6M14 10.5v6'),
  pencil: P('M4 20l1-4.5L16 4.5l3.5 3.5-11 11zM13.5 7l3.5 3.5'),
  shuffle: P('M4 7h3.5c4 0 5 10 9 10H20M17.5 14.5L20 17l-2.5 2.5M4 17h3.5c1.5 0 2.5-1.4 3.3-3M13.2 10c.8-1.6 1.8-3 3.3-3H20M17.5 4.5L20 7l-2.5 2.5'),
  flask: P('M9.5 3.5h5M10.5 3.5v6L4.8 18.6A1.3 1.3 0 0 0 6 20.5h12a1.3 1.3 0 0 0 1.2-1.9L13.5 9.5v-6M7.5 14.5h9'),
  grid: <g><rect x="4" y="4" width="6.5" height="6.5" rx="1" /><rect x="13.5" y="4" width="6.5" height="6.5" rx="1" /><rect x="4" y="13.5" width="6.5" height="6.5" rx="1" /><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1" /></g>,
  list: P('M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.2M4.5 12h.2M4.5 17.5h.2'),
  checklist: P('M4 7l2 2 3-3M4 15l2 2 3-3M12 7h8M12 15h8'),
  scan: P('M4 8.5V5.5A1.5 1.5 0 0 1 5.5 4h3M15.5 4h3A1.5 1.5 0 0 1 20 5.5v3M20 15.5v3a1.5 1.5 0 0 1-1.5 1.5h-3M8.5 20h-3A1.5 1.5 0 0 1 4 18.5v-3M8 12h8'),
  flag: P('M5.5 21V4M5.5 4.5h11l-2 4 2 4h-11'),
  target: <g><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="1" /></g>,
  wave: P('M3 12h3l2-6 3 12 3-9 2 6 2-3h3'),
  link: P('M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1'),
  'panel-left': <g><rect x="4" y="4.5" width="16" height="15" rx="2" />{P('M9.5 4.5v15')}</g>,
  'panel-right': <g><rect x="4" y="4.5" width="16" height="15" rx="2" />{P('M14.5 4.5v15')}</g>,
  'panel-bottom': <g><rect x="4" y="4.5" width="16" height="15" rx="2" />{P('M4 14.5h16')}</g>,
  more: P('M6 12h.2M12 12h.2M18 12h.2'),
  gauge: P('M4.5 17a8 8 0 1 1 15 0M12 13l3.5-4'),
  terminal: <g><rect x="3.5" y="4.5" width="17" height="15" rx="2" />{P('M7.5 9.5l3 2.5-3 2.5M12.5 15h4')}</g>,
  keyboard: <g><rect x="3" y="6.5" width="18" height="11" rx="2" />{P('M7 10h.2M10.5 10h.2M14 10h.2M17 10h.2M8 14h8')}</g>,
  monitor: <g><rect x="3.5" y="4.5" width="17" height="11.5" rx="1.5" />{P('M9 20h6M12 16v4')}</g>,
  user: <g><circle cx="12" cy="8.5" r="3.8" />{P('M4.5 20.5c1-4 4-6 7.5-6s6.5 2 7.5 6')}</g>,
  sparkle: P('M12 3.5l1.8 5.2 5.2 1.8-5.2 1.8L12 17.5l-1.8-5.2L5 10.5l5.2-1.8zM18.5 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z'),
  branch: <g><circle cx="6.5" cy="5.5" r="2" /><circle cx="6.5" cy="18.5" r="2" /><circle cx="17.5" cy="8" r="2" />{P('M6.5 7.5v9M17.5 10c0 4-11 3-11 6.5')}</g>,
} satisfies Record<string, ReactElement>

export type IconName = keyof typeof ICONS

const warned = new Set<string>()

export function Icon({ name, size = 14, strokeWidth = 1.7, className, style, title }: { name: IconName; size?: number; strokeWidth?: number; className?: string; style?: CSSProperties; title?: string }) {
  const g = ICONS[name]
  if (!g && !warned.has(name)) { warned.add(name); console.warn(`[kit] unknown icon "${name}"`) }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      className={`k-icon${className ? ' ' + className : ''}`} style={{ flex: 'none', ...style }} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined} data-icon={name}>
      {title && <title>{title}</title>}
      {g ?? <circle cx="12" cy="12" r="3" fill="currentColor" />}
    </svg>
  )
}
