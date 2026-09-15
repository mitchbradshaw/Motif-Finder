/* The page registry: every route in the web UI, the concept frames it covers, and the regions a
 * skeleton lays out until the page's builder replaces it. Mirrors webui/PAGES.md. Frames live in
 * prototyping/imgs/<folder>/<file>.pdf. */

export interface PageDef {
  id: string                 // e.g. 'models.launch'
  workspace: string          // Header workspace label
  title: string              // Header page label
  subtitle: string
  route: string              // canonical hash (no leading #/)
  frames: string[]           // prototyping/imgs paths
  regions: string[]          // main regions, top → bottom / left → right
}

const P = (id: string, workspace: string, title: string, subtitle: string, route: string, frames: string[], regions: string[]): PageDef =>
  ({ id, workspace, title, subtitle, route, frames, regions })

export const PAGES: PageDef[] = [
  P('explore.corpus', 'Explore', 'Corpus', "bird's-eye across every channel", 'explore/corpus', ['explore/explore-1-corpus', 'explore/explore-1b-corpus-menus'], ['toolbar', 'coverage map', 'filters rail', 'channel bottom bar']),
  P('explore.signal', 'Explore', 'Signal', 'one channel at real scale', 'explore/signal/4', ['explore/explore-2-signal', 'explore/explore-2a-signal-popovers', 'explore/explore-2b-signal-drawer', 'explore/explore-2c-drawer-detections', 'explore/explore-2d-drawer-shortcuts'], ['tier 1 channel', 'tier 2 span', 'tier 3 motif', 'span actions', 'drawer']),
  P('explore.cross-channel', 'Explore', 'Cross-channel', 'the same window on every channel', 'explore/cross-channel/4', ['explore/explore-3-cross-channel', 'explore/explore-3b-cross-channel-aligned'], ['toolbar', 'channel stack', 'lag panel']),
  P('explore.span-edit', 'Explore', 'Span edit', 'editing a span, opened from Review', 'explore/span-edit/m-1846', ['explore/explore-4-span-edit'], ['context strip', 'extent editor', 'revision panel']),
  P('analyse.chain', 'Analyse', 'Chain', 'build a chain, or import a template', 'analyse/chain', ['analyse-chain/chain-1-chain', 'analyse-chain/chain-1b-run-history', 'analyse-chain/chain-1c-empty-import-template', 'analyse-chain/chain-1d-running', 'analyse-chain/chain-1e-invalid-junction', 'analyse-chain/chain-1f-failed-block', 'analyse-chain/chain-1g-heavy-stage-hpc', 'analyse-chain/chain-1h-scores-chain', 'analyse-chain/chain-1i-paused-result-in-place', 'analyse-chain/chain-2-insert-stage'], ['toolbar', 'chain rows', 'terminal footer']),
  P('analyse.block', 'Analyse', 'Block', 'settings and output together', 'analyse/block/1', ['analyse-chain/chain-3-block03-symbolic-encoding', 'analyse-chain/chain-4-block04-drop-detection', 'analyse-chain/chain-5-block01-baseline-removal', 'analyse-chain/chain-6-block02-noise-floor', 'analyse-chain/chain-7-block-matrix-profile-scores', 'analyse-chain/chain-7b-block-threshold-to-spans', 'analyse-chain/chain-8-block-model-stage'], ['chain ribbon', 'block output', 'parameters', 'null sweep']),
  P('analyse.glyphs', 'Analyse', 'Algorithm glyphs', 'the glyph registry', 'analyse/glyphs', ['analyse-chain/chain-6b-algorithm-glyphs'], ['glyph grid']),
  P('analyse.interrogation', 'Analyse', 'Interrogation', 'source block: the family being analysed', 'analyse/interrogation', ['analyse-interrogation/interrogation-1-family-block', 'analyse-interrogation/interrogation-1b-source-picker'], ['toolbar', 'chain ribbon', 'family members', 'source picker']),
  P('analyse.interrogation.slope', 'Analyse', 'Interrogation · 01 Slope', 'slope analysis', 'analyse/interrogation/block/1', ['analyse-interrogation/interrogation-2-block01-slope', 'analyse-interrogation/interrogation-2b-slope-large-family', 'analyse-interrogation/interrogation-2c-slope-stale-after-edit'], ['chain ribbon', 'member strip', 'slope distributions', 'rules']),
  P('analyse.interrogation.aggregate', 'Analyse', 'Interrogation · 02 Aggregate', 'aggregate', 'analyse/interrogation/block/2', ['analyse-interrogation/interrogation-3-block02-aggregate', 'analyse-interrogation/interrogation-3b-aggregate-colour-by-recording', 'analyse-interrogation/interrogation-3c-aggregate-wired-from-spike-shape'], ['chain ribbon', 'relationship plot', 'fit + null', 'settings']),
  P('analyse.training', 'Analyse', 'Training', 'built on one channel, applied across the corpus', 'analyse/training', ['analyse-training/training-0-training-chain', 'analyse-training/training-0b-human-window-source-ILLUSTRATIVE'], ['toolbar', 'training chain rows', 'hand-off footer']),
  P('analyse.training.windows', 'Analyse', 'Training · 01 Sliding windows', 'windows, stride and the blocked split', 'analyse/training/block/1', ['analyse-training/training-01-block01-sliding-windows'], ['chain ribbon', 'windows on the channel', 'split', 'parameters']),
  P('analyse.training.matrix', 'Analyse', 'Training · 02 Window matrix', 'features per window', 'analyse/training/block/2', ['analyse-training/training-1-block02-window-matrix'], ['chain ribbon', 'feature matrix', 'feature groups']),
  P('analyse.training.cluster', 'Analyse', 'Training · 03 Cluster', 'clusters and choosing k', 'analyse/training/block/3', ['analyse-training/training-2-block03-cluster', 'analyse-training/training-2b-block03-choose-k'], ['chain ribbon', 'cluster map', 'members', 'choose k']),
  P('analyse.training.encode', 'Analyse', 'Training · 04 Encode', 'image encodings', 'analyse/training/block/4', ['analyse-training/training-3-block04-encode'], ['chain ribbon', 'encoded images', 'encoder set']),
  P('analyse.training.model', 'Analyse', 'Training · 05 Model', 'model', 'analyse/training/block/5', ['analyse-training/training-4-block05-model'], ['chain ribbon', 'model card', 'train in Models']),
  P('discovery.runs', 'Discovery', 'Runs', 'apply templates and seeds across channels', 'discovery/runs', ['discovery/discovery-1-runs', 'discovery/discovery-1b-add-template', 'discovery/discovery-1c-many-channels'], ['toolbar', 'runs list', 'where each run fires', 'scoreboard', 'browser']),
  P('discovery.seed', 'Discovery', 'Seed search', 'set up a seed run', 'discovery/seed', ['discovery/discovery-2-seed'], ['seed', 'scope', 'matching', 'estimate']),
  P('discovery.compare', 'Discovery', 'Compare', 'template run A against seed run B', 'discovery/compare', ['discovery/discovery-3-compare'], ['run pickers', 'agreement', 'disagreements']),
  P('discovery.stages', 'Discovery', 'Compare every stage', 'one disagreement pushed through both runs', 'discovery/compare/stages', ['discovery/discovery-3b-stages'], ['stage pairs', 'divergence']),
  P('models.launch', 'Models', 'Launch', 'train a template across channels · paired label arms', 'models/launch', ['models/models-1-launch', 'models/models-1b-launch-from-window-set'], ['toolbar + tabs', 'training template', 'sources', 'label arms', 'evaluation', 'options', 'before launch']),
  P('models.results', 'Models', 'Results', 'one arm on the test block, against baseline and nulls', 'models/results', ['models/models-3-results'], ['tabs', 'arm summary', 'nulls', 'calibration']),
  P('models.compare', 'Models', 'Compare', 'manual vs cluster labels, paired', 'models/compare', ['models/models-4-compare', 'models/models-4b-compare-both-wrong'], ['tabs', 'paired metrics', 'disagreement windows']),
  P('models.registry', 'Models', 'Registry', 'register with held-out checks and sign-off', 'models/registry', ['models/models-5-registry'], ['tabs', 'registered models', 'candidate checks', 'sign-off']),
  P('review.inspector', 'Review', 'Queue', 'one candidate at a time', 'review/queue/q-12', ['review/review-1-candidate', 'review/review-1b-other-channels', 'review/review-3-queue-open', 'review/review-4-evidence-open', 'review/review-5-blind-verification', 'review/review-6-seed-promoted'], ['queue rail', 'candidate', 'verdict bar', 'evidence rail']),
  P('review.cluster', 'Review', 'Cluster', 'seed-search matches with member strip', 'review/queue/q-15/cluster/12', ['review/review-2-cluster', 'review/review-7-batch-undone'], ['cluster', 'member strip', 'verdicts']),
  P('library.recurrence', 'Library', 'Recurrence', 'where each family occurs, per hour', 'library/recurrence', ['library/library-1-recurrence'], ['section tabs', 'recurrence raster', 'families']),
  P('library.atlas', 'Library', 'Atlas', 'grouped by shape', 'library/atlas', ['library/library-2-atlas-motifs', 'library/library-2b-atlas-sequences'], ['grouping bar', 'family grid', 'detail']),
  P('library.family', 'Library', 'Family', 'exemplar and medoid, every member, hand edits', 'library/family/F-03', ['library/library-3-family'], ['family header', 'overlay', 'members']),
  P('library.grouping', 'Library', 'Edit grouping', 'unit, basis, what does not fit, hand edits', 'library/grouping', ['library/library-4-edit-grouping'], ['unit', 'basis', 'omitted', 'hand edits']),
  P('library.import', 'Library', 'Import', 'empty library and the motif import (dry run)', 'library/import', ['library/library-5-empty-import'], ['empty state', 'import dry run']),
  P('library.window-sets', 'Library', 'Window sets', 'saved, reusable, with split and train-safety', 'library/window-sets', ['library/library-6-window-sets'], ['set list', 'set detail']),
  P('library.templates', 'Library', 'Templates', 'every saved chain, its versions and scores', 'library/templates', ['library/library-7-templates'], ['template list', 'versions', 'scores']),
  P('jobs.all', 'Jobs', 'All jobs', 'every job across workspaces', 'jobs', ['jobs/jobs-1-all'], ['needs you', 'jobs table']),
  P('jobs.paused', 'Jobs', 'Paused run', 'where it stopped; its result arrived in place', 'jobs/run/a-0098', ['jobs/jobs-2-paused-run'], ['run stages', 'result check', 'continue']),
  P('jobs.upload', 'Jobs', 'Upload and continue', 'checked before placing', 'jobs/run/r-0431/upload', ['jobs/jobs-3-upload-and-continue'], ['upload', 'checks', 'continue']),
  P('jobs.cluster', 'Jobs', 'Cluster job', 'hand-marked status, reminder, script, manifest inbox', 'jobs/cluster/j-0217', ['jobs/jobs-4-cluster-job-inbox'], ['job', 'status', 'script', 'manifest inbox']),
  ...([
    ['datasets', 'Datasets', 'settings-01-datasets'], ['channels-events', 'Channels & events', 'settings-02-channels-events'], ['vocabulary', 'Vocabulary', 'settings-03-vocabulary'],
    ['nulls', 'Nulls', 'settings-04-nulls'], ['analysis-defaults', 'Analysis defaults', 'settings-05-analysis-defaults'], ['compute-hpc', 'Compute & HPC', 'settings-06-compute-hpc'],
    ['blocks', 'Blocks', 'settings-07-blocks'], ['review-queues', 'Review queues', 'settings-08-review-queues'], ['models-registration', 'Models & registration', 'settings-09-models-registration'],
    ['library-groupings', 'Library groupings', 'settings-10-library-groupings'], ['storage-backups', 'Storage & backups', 'settings-11-storage-backups'], ['export', 'Export', 'settings-12-export'],
    ['audit-log', 'Audit log', 'settings-13-audit-log'], ['about', 'About', 'settings-14-about'], ['display', 'Display', 'settings-15-display'], ['keyboard', 'Keyboard & behaviour', 'settings-16-keyboard-behaviour'],
  ] as const).map(([slug, title, frame]) => P(`settings.${slug}`, 'Settings', title, ['display', 'keyboard'].includes(slug) ? 'personal · this browser' : 'project · recorded with runs', `settings/${slug}`,
    slug === 'datasets' ? [`settings/${frame}`, 'settings/settings-01b-import-recording'] : [`settings/${frame}`], ['settings nav', 'page sections'])),
]

export const pageById = (id: string) => PAGES.find(p => p.id === id)
