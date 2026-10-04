"""Q40d -- statistics and plots from pairs.csv / members.csv (made by measure.py). Read-only on the DB and the .npy.

Writes stats.json and the PNGs next to this file.
"""
import json, os, sqlite3, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

ROOT = 'C:/Users/mmebr/Documents/CNN'
sys.path.insert(0, ROOT)
from Working import cross_channel as xc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DB = ROOT + '/webui/runtime/20261004-184434/annotations.sqlite'
NOISE = 0.1
SCALE = {'V': 1000.0, 'mV': 1.0}
POS, NEG = '#2a6fdb', '#e8743b'
CH_COL = plt.get_cmap('tab10').colors
FAM_COL = {'F-130': '#1b9e77', 'F-119': '#d95f02', 'F-39': '#7570b3'}
plt.rcParams.update({'font.size': 9, 'axes.titlesize': 9.5, 'figure.dpi': 110})

c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
c.row_factory = sqlite3.Row
recs = {}
for r in c.execute('SELECT * FROM recordings'):
    recs.setdefault(r['source_file'], {})[r['channel']] = dict(r)
_arr = {}


def chan(sf, ch):
    rec = recs[sf][ch]
    k = rec['npy_path']
    if k not in _arr:
        assert 'M4_aug_concat' not in k
        _arr[k] = np.load(os.path.join(ROOT, k), mmap_mode='r')
    return _arr[k], SCALE[rec['units']], rec


p = pd.read_csv(os.path.join(HERE, 'pairs.csv'))
m = pd.read_csv(os.path.join(HERE, 'members.csv'))
# W's stored verdict: an artifact co-occurrence row, or an artifact-binned edge to another member
_ids = set(m.member_id)
_co = {r[0] for r in c.execute("SELECT member_id FROM motif_member_cooccurrence WHERE classification_bin='artifact'")}
_ed = set()
for a, b in c.execute("SELECT member_a_id, member_b_id FROM motif_edge WHERE classification_bin='artifact'"):
    if a in _ids and b in _ids:
        _ed |= {a, b}
m['stored_flag'] = m.member_id.isin(_co | _ed)
p['abs_r'] = p.r.abs()
p['strict'] = (p.same_instant & (p.abs_r >= 0.9) & p.amp_ratio.between(0.5, 2)
               & p.sib_clears_floor & p.member_clears_floor)
m['strict_flag'] = m.member_id.isin(p[p.strict].member_id)
m['own_flag'] = m.member_id.isin(p[p.same_instant].member_id)
S = {}

# ---------------------------------------------------------------- numbers
si = p[p.same_instant].copy()
si['stratum'] = pd.cut(si.abs_r, [0.5, 0.7, 0.9, 1.0001], right=False, labels=['0.5-0.7', '0.7-0.9', '0.9-1.0'])
S['strata'] = {}
for k, g in si.groupby('stratum', observed=True):
    S['strata'][k] = dict(n=len(g), median_amp_ratio=round(g.amp_ratio.median(), 3),
                          iqr=[round(g.amp_ratio.quantile(.25), 3), round(g.amp_ratio.quantile(.75), 3)],
                          pct_ratio_0p5_to_2=round(100 * g.amp_ratio.between(.5, 2).mean(), 1),
                          pct_sib_clears_floor=round(100 * g.sib_clears_floor.mean(), 1),
                          pct_both_clear_floor=round(100 * (g.sib_clears_floor & g.member_clears_floor).mean(), 1),
                          pct_negative_r=round(100 * (g.r < 0).mean(), 1),
                          pct_lag_zero=round(100 * (g.lag_samples == 0).mean(), 1),
                          by_file={sf: dict(n=len(h), median_amp_ratio=round(h.amp_ratio.median(), 3),
                                            pct_sib_clears_floor=round(100 * h.sib_clears_floor.mean(), 1))
                                   for sf, h in g.groupby('source_file')})
S['same_instant_rows'] = len(si)
S['pct_negative_r_same_instant'] = round(100 * (si.r < 0).mean(), 1)
S['pairs_total'] = len(p)
S['members'] = len(m)
S['members_flagged_stored_W'] = int(m.stored_flag.sum()) if 'stored_flag' in m.columns else None
S['members_flagged_own_span'] = int(m.own_flag.sum())
S['members_flagged_strict'] = int(m.strict_flag.sum())
S['member_ptp_mV'] = dict(median=round(m.ptp_mV.median(), 3), pct_clear_floor=round(100 * (m.ptp_mV >= NOISE).mean(), 1))
S['span_samples_median_by_file'] = p.drop_duplicates('member_id').groupby('source_file').n.median().to_dict()
# random-time control
S['control'] = {}
for sf, g in p.groupby('source_file'):
    S['control'][sf] = dict(pairs=len(g), real_rule_pass=round(100 * g.same_instant.mean(), 1),
                            random_time_rule_pass=round(100 * g.null_same_instant_frac.mean(), 1),
                            real_strict_pass=round(100 * g.strict.mean(), 1),
                            random_time_strict_pass=round(100 * g.null_strict_frac.mean(), 1))
# expected members flagged if every sibling were cut at a random other time
exp_rule = (1 - (1 - p.null_same_instant_frac).groupby(p.member_id).prod()).sum()
exp_strict = (1 - (1 - p.null_strict_frac).groupby(p.member_id).prod()).sum()
S['expected_members_flagged_at_random_times'] = dict(rule=round(float(exp_rule), 1), strict=round(float(exp_strict), 1))

# ---------------------------------------------------------------- annotations (human artifact regions)
ann = pd.read_sql("""SELECT a.recording_id, r.source_file, r.channel, a.start_idx, a.end_idx, a.verdict
                       FROM annotations a JOIN recordings r ON r.id = a.recording_id
                      WHERE a.verdict = 'artifact' AND a.deleted_at IS NULL""", c)
S['fig2a_parent'] = [dict(channel=r['channel'], parent_recording_id=r['parent_recording_id'],
                          parent_offset=r['parent_offset'], decimation=r['decimation'])
                     for r in recs['Fig2A_dt0p1.csv'].values()]
S['artifact_annotations_by_file'] = ann.groupby('source_file').size().to_dict()
m2 = m[m.source_file == 'M2_aug_concat_fs1.mat']
a2 = ann[ann.source_file == 'M2_aug_concat_fs1.mat']
N2 = recs['M2_aug_concat_fs1.mat'][0]['n_samples']
cover = np.zeros(N2, bool)
for _, a in a2.iterrows():
    cover[a.start_idx:a.end_idx] = True


def near(row, pad):
    return bool(cover[max(0, row.start - pad):min(N2, row.end + pad)].any())


S['m2_overlap'] = dict(
    members=len(m2), recording_fraction_marked_artifact_any_channel=round(float(cover.mean()), 4),
    members_inside_artifact_region=int(sum(near(r, 0) for r in m2.itertuples())),
    members_within_30min=int(sum(near(r, 1800) for r in m2.itertuples())),
    members_within_2h=int(sum(near(r, 7200) for r in m2.itertuples())),
    expected_within_30min_if_uniform=round(float(np.mean([cover[max(0, t - 1800):t + 1800 + 540].any()
                                                           for t in np.linspace(0, N2 - 1, 4000).astype(int)]) * len(m2)), 1))

# ---------------------------------------------------------------- clustering in time
def clustering(df, flag, fs, win_s, rng=np.random.default_rng(1), nperm=2000):
    """Members pooled across channels, sorted by onset. Gaps between consecutive flagged members (and between
    consecutive unflagged ones); fraction of flagged members with another flagged member starting within win_s,
    against the same fraction when the flags are shuffled among the same members (permutation)."""
    t = df.start.values / fs
    f = df[flag].values.astype(bool)

    def frac(fl):
        tt = np.sort(t[fl])
        if len(tt) < 2:
            return np.nan
        d = np.diff(tt)
        nn = np.minimum(np.r_[np.inf, d], np.r_[d, np.inf])
        return float((nn <= win_s).mean())

    def gaps(fl):
        tt = np.sort(t[fl])
        return np.diff(tt)

    obs = frac(f)
    perm = np.array([frac(rng.permutation(f)) for _ in range(nperm)])
    return dict(n_flagged=int(f.sum()), n_unflagged=int((~f).sum()),
                median_gap_flagged_s=round(float(np.median(gaps(f))), 1) if f.sum() > 1 else None,
                median_gap_unflagged_s=round(float(np.median(gaps(~f))), 1) if (~f).sum() > 1 else None,
                frac_flagged_within=round(obs, 3), window_s=win_s,
                perm_mean=round(float(np.nanmean(perm)), 3),
                perm_p_ge=round(float(np.mean(perm >= obs)), 4)), gaps(f), gaps(~f)


fg = m[m.source_file == 'Fig2A_dt0p1.csv']
S['clustering'] = {}
cl_fig, gf, gu = clustering(fg, 'strict_flag', 10.0, 30.0)
S['clustering']['Fig2A_strict_30s'] = cl_fig
S['clustering']['Fig2A_strict_60s'] = clustering(fg, 'strict_flag', 10.0, 60.0)[0]
# the events themselves: are members (whatever the flag) bunched? coefficient of variation of gaps (1 = Poisson)
tt = np.sort(fg.start.values / 10.0)
d = np.diff(tt)
S['clustering']['Fig2A_all_members_gap_cv'] = round(float(d.std() / d.mean()), 2)
S['clustering']['Fig2A_all_members_pct_gap_le_5s'] = round(100 * float((d <= 5).mean()), 1)
S['clustering']['M2_strict_30min'] = clustering(m2, 'strict_flag', 1.0, 1800.0)[0]

with open(os.path.join(HERE, 'stats.json'), 'w') as f:
    json.dump(S, f, indent=1, default=str)
print(json.dumps(S, indent=1, default=str))


# ---------------------------------------------------------------- A. galleries
def pick(df, k, seed):
    rng = np.random.default_rng(seed)
    out = []
    fg_ = df[df.source_file == 'Fig2A_dt0p1.csv']
    m2_ = df[df.source_file != 'Fig2A_dt0p1.csv']
    take_m2 = 1 if len(m2_) else 0
    out += list(fg_.sample(min(k - take_m2, len(fg_)), random_state=int(rng.integers(1e6))).index)
    if take_m2:
        out += list(m2_.sample(1, random_state=int(rng.integers(1e6))).index)
    return df.loc[out]


ex = []
for lab, lo, hi, seed in (('|r| 0.9-1.0', .9, 1.01, 1), ('|r| 0.7-0.9', .7, .9, 2), ('|r| 0.5-0.7', .5, .7, 3)):
    g = si[(si.abs_r >= lo) & (si.abs_r < hi)].drop_duplicates('member_id')
    for _, r in pick(g, 4, seed).iterrows():
        ex.append((lab, r, None))
unflag = m[~m.stored_flag] if 'stored_flag' in m.columns else m.iloc[:0]
for _, mr in unflag.iterrows():
    sib = p[p.member_id == mr.member_id].sort_values('abs_r', ascending=False).iloc[0]
    ex.append(('NOT flagged by W', sib, None))


def random_control(seed):
    """A member against its sibling cut at a random OTHER time (>= 60 s away) that still passes W's rule."""
    rng = np.random.default_rng(seed)
    cand = p[p.source_file == 'Fig2A_dt0p1.csv']
    while True:
        r = cand.iloc[int(rng.integers(len(cand)))]
        y_arr, sc, rec = chan(r.source_file, int(r.sib_ch))
        x_arr, scx, _ = chan(r.source_file, int(r.member_ch))
        n = int(r.n)
        x = np.asarray(x_arr[r.start:r.start + n], float) * scx
        for _ in range(50):
            t0 = int(rng.integers(0, rec['n_samples'] - n))
            if abs(t0 - r.start) < 600:
                continue
            y = np.asarray(y_arr[t0:t0 + n], float) * sc
            lag, rr, cls = xc.classify_waveforms(x, y, fs=10.0)
            if cls == xc.ARTIFACT and abs(rr) >= 0.9:
                return r, t0, lag, rr, float(np.ptp(y) / np.ptp(x))


while len(ex) < 16:
    ex.append(('CONTROL: sibling at a random other time', None, random_control(len(ex) * 7)))


def panel(ax, lab, r, ctrl, mode):
    if ctrl is not None:
        r, t0, lag, rr, ratio = ctrl
    sf, fs = r.source_file, float(r.fs)
    s0, s1 = int(r.start), int(r.end)
    span = s1 - s0
    a0, a1 = max(0, s0 - span), min(recs[sf][0]['n_samples'], s1 + span)
    tt = (np.arange(a0, a1) - s0) / fs
    chans = sorted(recs[sf])
    rows = p[p.member_id == r.member_id].set_index('sib_ch')
    txt = []
    for ch in chans:
        arr, sc, _ = chan(sf, ch)
        is_m = ch == int(r.member_ch)
        if ctrl is not None and not is_m and ch != int(r.sib_ch):
            continue
        if ctrl is not None and not is_m:
            off = t0 - s0
            y = np.asarray(arr[a0 + off:a1 + off], float) * sc
        else:
            y = np.asarray(arr[a0:a1], float) * sc
        if mode == 'mV':
            y = y - np.median(y)
        else:
            seg = y[s0 - a0:s1 - a0]
            y = (y - seg.mean()) / (seg.std() or 1)
        is_ex = (not is_m) and ch == int(r.sib_ch)
        many = len(chans) > 6
        if is_m:
            kw = dict(color='k', lw=2.2, zorder=5)
        elif is_ex:
            kw = dict(color=CH_COL[ch % 10], lw=1.6, zorder=4)
        else:
            kw = dict(color=(0.6, 0.6, 0.6) if many else CH_COL[ch % 10], lw=0.6 if many else 0.9, alpha=0.8, zorder=2)
        ax.plot(tt, y, **kw)
        if not is_m and ctrl is None and ch in rows.index:
            q = rows.loc[ch]
            if many and not is_ex:
                continue
            flag = '*' if q.same_instant else ' '
            txt.append((f"{flag}CH{ch + 1}: r {q.r:+.2f}, lag {q.lag_s:+.1f} s, amp x{q.amp_ratio:.2f}", kw['color']))
    if ctrl is not None:
        txt.append((f"*CH{int(r.sib_ch) + 1} @ {(t0 - s0) / fs:+.0f} s: r {rr:+.2f}, lag {lag / fs:+.1f} s, amp x{ratio:.2f}",
                    CH_COL[int(r.sib_ch) % 10]))
    if len(chans) > 6 and ctrl is None:
        txt.append((f"(+{len(chans) - 2} other channels in grey)", (0.4, 0.4, 0.4)))
    ax.axvspan(0, span / fs, color='#ffd54f', alpha=0.25, zorder=0)
    ax.set_xlim(tt[0], tt[-1])
    name = 'Fig2A' if sf.startswith('Fig2A') else 'M2_aug'
    ax.set_title(f"[{lab}]\n{r.fam} m-{r.member_id} · {name} CH{int(r.member_ch) + 1} (bold) · "
                 f"t={s0 / fs:.0f} s · {span / fs:.1f} s span · ptp {r.ptp_member_mV:.2f} mV", loc='left')
    ax.set_xlabel('time from member onset (s)')
    ax.set_ylabel('mV (minus own median)' if mode == 'mV' else 'z (by member-span mean/sd)')
    for i, (t_, col) in enumerate(txt):
        ax.text(0.01, 0.97 - 0.085 * i, t_, transform=ax.transAxes, fontsize=7.2, color=col, va='top',
                family='monospace', bbox=dict(fc='white', ec='none', alpha=0.7, pad=0.5))


for mode, fname, cap in (
        ('mV', 'examples_gallery_mV.png',
         'TRUE SCALE: every channel in mV on one shared y-axis per panel; each trace only has its own median (over '
         'the window shown) subtracted. Member channel bold black, shaded = member span, padded by 1x span each side.'),
        ('z', 'examples_gallery_zscore.png',
         'SHAPE VIEW: each channel z-scored by its own mean/sd over the member span, then overlaid (scale removed). '
         'Member channel bold black, shaded = member span.')):
    fig, axes = plt.subplots(4, 4, figsize=(22, 17))
    for ax, (lab, r, ctrl) in zip(axes.flat, ex):
        panel(ax, lab, r, ctrl, mode)
    fig.suptitle('Q40d - same-instant cross-channel matches, F-130 / F-119 / F-39 (g-05). Rows 1-3: one example sibling '
                 'per panel in the |r| stratum named (coloured bold); * = passes W\'s artifact rule (|lag|<=1 s, |r|>=0.5).\n'
                 'Row 4: the 2 members W left unflagged, then CONTROLS: the member against its sibling cut at a RANDOM '
                 'OTHER time (>= 60 s away) that still passes the rule at |r| >= 0.9.\n' + cap, fontsize=10.5, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(os.path.join(HERE, fname))
    plt.close(fig)

# ---------------------------------------------------------------- B. scatter
fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), sharey=True)
for ax, sf in zip(axes, ('Fig2A_dt0p1.csv', 'M2_aug_concat_fs1.mat')):
    g = si[si.source_file == sf]
    for sign, col, lab in ((1, POS, 'r > 0'), (-1, NEG, 'r < 0 (inverted)')):
        h = g[np.sign(g.r) == sign]
        ok = h[h.sib_clears_floor]
        bad = h[~h.sib_clears_floor]
        ax.scatter(ok.amp_ratio, ok.abs_r, s=16, color=col, alpha=0.7, label=f'{lab}, sibling ptp >= {NOISE} mV')
        ax.scatter(bad.amp_ratio, bad.abs_r, s=26, color=col, marker='x', alpha=0.9,
                   label=f'{lab}, sibling ptp < {NOISE} mV (noise floor)')
    ax.set_xscale('log')
    ax.axvspan(0.5, 2, color='0.9', zorder=0)
    ax.axvline(1, color='0.5', lw=0.8)
    ax.axhline(0.9, color='0.5', lw=0.8, ls='--')
    cs = S['control'][sf]
    ax.set_title(f"{sf} - {len(g)} same-instant rows (|lag| <= 1 s, |r| >= 0.5), all sibling channels\n"
                 f"rule passes on {cs['real_rule_pass']}% of real sibling windows vs {cs['random_time_rule_pass']}% "
                 f"at random other times;\nstrict (|r|>=0.9, ratio 0.5-2, both >= 0.1 mV): {cs['real_strict_pass']}% "
                 f"real vs {cs['random_time_strict_pass']}% random", loc='left')
    ax.set_xlabel('amplitude ratio = ptp(sibling) / ptp(member), both in mV (log); grey band = within 2x')
axes[0].set_ylabel('|r| (peak cross-correlation, member own span)')
axes[0].legend(fontsize=7.5, loc='lower left')
fig.tight_layout()
fig.savefig(os.path.join(HERE, 'scatter_r_vs_amplitude_ratio.png'))
plt.close(fig)

# ---------------------------------------------------------------- C. timeline
fig = plt.figure(figsize=(16, 11))
gs = fig.add_gridspec(3, 2, height_ratios=[1.1, 1.6, 1], hspace=0.45)
ax = fig.add_subplot(gs[0, :])
for _, r in fg.iterrows():
    y = int(r.channel) + 1
    col = '#c62828' if r.strict_flag else ('#f9a825' if r.get('stored_flag', True) else '#2e7d32')
    ax.plot([r.start / 10 / 60, r.end / 10 / 60], [y, y], color=col, lw=9, solid_capstyle='butt')
ax.set_yticks(range(1, 6), [f'CH{i}' for i in range(1, 6)])
ax.set_ylim(0.4, 5.6)
ax.set_xlim(0, 1200 / 60)
ax.set_xlabel('time in Fig2A_dt0p1 (min)')
ax.set_title('Fig2A_dt0p1 - 114 members of F-130/F-119/F-39 by channel. No human artifact regions exist for Fig2A '
             '(0 annotations; no parent_recording_id, so nothing to map from a parent).', loc='left')
ax.legend(handles=[Patch(color='#c62828', label='strict flag: a sibling at |lag|<=1 s, |r|>=0.9, amplitude within 2x, both >= 0.1 mV'),
                   Patch(color='#f9a825', label="flagged by W's stored rule only (|r|>=0.5)"),
                   Patch(color='#2e7d32', label='not flagged by W')], fontsize=7.5, loc='upper right', ncol=3)
ax = fig.add_subplot(gs[1, :])
for ch in range(16):
    for _, a in a2[a2.channel == ch].iterrows():
        ax.axvspan(a.start_idx / 86400, a.end_idx / 86400, ymin=(ch + .1) / 16, ymax=(ch + .9) / 16, color='#9e9e9e', alpha=0.9)
for _, r in m2.iterrows():
    col = '#c62828' if r.strict_flag else '#f9a825'
    ax.plot([r.start / 86400], [int(r.channel) + 0.5], marker='v', ms=9, color=col, mec='k')
ax.set_ylim(0, 16)
ax.set_yticks(np.arange(16) + .5, [f'CH{i + 1}' for i in range(16)], fontsize=7)
ax.set_xlim(0, N2 / 86400)
ax.set_xlabel('time in M2_aug_concat_fs1 (days, 1 Hz)')
o = S['m2_overlap']
ax.set_title(f"M2_aug_concat_fs1 - 21 members (triangles: red strict, amber W-only) and human 'artifact' annotations "
             f"(grey, 10-min windows, per channel; {len(a2)} of them, {100 * o['recording_fraction_marked_artifact_any_channel']:.1f}% "
             f"of the time on some channel).\nMembers inside a marked region: {o['members_inside_artifact_region']}; within 30 min: "
             f"{o['members_within_30min']} (expected if placed at random: {o['expected_within_30min_if_uniform']}).", loc='left')
ax = fig.add_subplot(gs[2, 0])
bins = np.logspace(-1, 3, 25)
ax.hist(np.maximum(gf, 0.1), bins=bins, alpha=0.6, color='#c62828', label=f'strict-flagged (n={len(gf) + 1})')
ax.hist(np.maximum(gu, 0.1), bins=bins, alpha=0.6, color='#1565c0', label=f'not strict-flagged (n={len(gu) + 1})')
ax.set_xscale('log')
ax.set_xlabel('gap to next member of the same group, pooled over channels (s, log; 0 shown at 0.1)')
ax.set_ylabel('count')
ax.legend(fontsize=8)
ax.set_title(f"Fig2A gaps: median {cl_fig['median_gap_flagged_s']} s (strict) vs {cl_fig['median_gap_unflagged_s']} s (rest)", loc='left')
ax = fig.add_subplot(gs[2, 1])
ax.axis('off')
cs = S['clustering']
ax.text(0, 1, '\n'.join([
    'Clustering (Fig2A, members pooled over channels):',
    f"  strict-flagged with another strict-flagged member <= 30 s away: {cs['Fig2A_strict_30s']['frac_flagged_within']:.0%}",
    f"  same, flags shuffled among the 114 members (2000x): {cs['Fig2A_strict_30s']['perm_mean']:.0%}  (p = {cs['Fig2A_strict_30s']['perm_p_ge']})",
    f"  at 60 s: {cs['Fig2A_strict_60s']['frac_flagged_within']:.0%} vs {cs['Fig2A_strict_60s']['perm_mean']:.0%} shuffled (p = {cs['Fig2A_strict_60s']['perm_p_ge']})",
    f"  all members: gap CV {cs['Fig2A_all_members_gap_cv']} (1 = random/Poisson), {cs['Fig2A_all_members_pct_gap_le_5s']}% of gaps <= 5 s",
    '',
    'M2_aug (21 members over 30 days):',
    f"  strict-flagged within 30 min of another: {cs['M2_strict_30min']['frac_flagged_within']} vs shuffled {cs['M2_strict_30min']['perm_mean']} (p = {cs['M2_strict_30min']['perm_p_ge']})",
]), va='top', family='monospace', fontsize=8.5)
fig.suptitle('Q40d - are the flagged members bunched in time, and do they sit in human-marked artifact regions?', fontsize=11)
fig.savefig(os.path.join(HERE, 'timeline.png'), bbox_inches='tight')
plt.close(fig)

# ---------------------------------------------------------------- D. overviews
fig, axes = plt.subplots(3, 1, figsize=(18, 14), sharex=True)
t = np.arange(recs['Fig2A_dt0p1.csv'][0]['n_samples']) / 10 / 60
gapmv = 2.0
for ax, fam in zip(axes, ('F-130', 'F-119', 'F-39')):
    for ch in range(5):
        arr, sc, _ = chan('Fig2A_dt0p1.csv', ch)
        y = np.asarray(arr, float) * sc
        y = y - np.median(y)
        off = -ch * gapmv
        ax.plot(t, y + off, color=CH_COL[ch], lw=0.5)
        ax.text(-0.3, off, f'CH{ch + 1}', ha='right', va='center', color=CH_COL[ch])
        for _, r in fg[(fg.fam == fam) & (fg.channel == ch)].iterrows():
            seg = slice(int(r.start), int(r.end))
            ax.plot(t[seg], y[seg] + off, color='#c62828' if r.strict_flag else 'k', lw=2.2)
    ax.set_title(f'{fam} on Fig2A_dt0p1 - raw, all 5 channels in mV (each minus its median, stacked {gapmv} mV apart; '
                 f'no decimation: 12,001 samples). Members drawn thick: red = strict flag, black = other', loc='left')
    ax.set_ylabel(f'mV (offset {gapmv} mV per channel)')
axes[-1].set_xlabel('time (min)')
fig.tight_layout()
fig.savefig(os.path.join(HERE, 'overview_Fig2A_by_family.png'))
plt.close(fig)

fig, ax = plt.subplots(figsize=(18, 12))
nb = 6000
edges = np.linspace(0, N2, nb + 1).astype(int)
for ch in range(16):
    arr, sc, _ = chan('M2_aug_concat_fs1.mat', ch)
    x = np.asarray(arr, float) * sc
    lo = np.minimum.reduceat(x, edges[:-1])
    hi = np.maximum.reduceat(x, edges[:-1])
    med = np.median(x[::50])
    rng_ = np.percentile(hi - lo, 99) or 1
    off = -ch
    tb = edges[:-1] / 86400
    ax.fill_between(tb, (lo - med) / (4 * rng_) + off, (hi - med) / (4 * rng_) + off, color=CH_COL[ch % 10], lw=0, alpha=0.8)
    for _, a in a2[a2.channel == ch].iterrows():
        ax.axvspan(a.start_idx / 86400, a.end_idx / 86400, ymin=(15 - ch + .05) / 16.5, ymax=(15 - ch + .95) / 16.5, color='0.6', alpha=0.5)
for _, r in m2.iterrows():
    ax.plot(r.start / 86400, -int(r.channel), marker='v', ms=11, color=FAM_COL[r.fam], mec='k', zorder=6)
ax.set_yticks(-np.arange(16), [f'CH{i + 1}' for i in range(16)])
ax.set_ylim(-15.75, 0.75)
ax.set_xlabel('time (days, 1 Hz)')
ax.set_title('M2_aug_concat_fs1 - min/max envelope per bin (6000 bins, never interpolated), each channel scaled to its own '
             '99th-pct bin range (NOT a shared mV scale); grey = human artifact annotations;\ntriangles = members '
             '(F-130 green, F-119 orange, F-39 purple)', loc='left')
ax.legend(handles=[Line2D([], [], marker='v', ls='', color=v, mec='k', label=k) for k, v in FAM_COL.items()] +
          [Patch(color='0.6', alpha=0.5, label="human 'artifact' (10-min)")], loc='lower right')
fig.tight_layout()
fig.savefig(os.path.join(HERE, 'overview_M2_aug.png'))
plt.close(fig)
print('done')
