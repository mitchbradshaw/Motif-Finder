"""Q40d -- read-only measurement of same-instant cross-channel matches for F-130 / F-119 / F-39 (grouping g-05).

For every member and every other channel of its recording, the member's own span (unpadded) is cut from both
channels at the SAME absolute samples and passed to Working.cross_channel.classify_waveforms -- the exact function
fixup W used -- so lag and r are recomputed, not re-derived. Added here: amplitude (peak-to-peak, mV) on both
channels, the ratio, and the 0.1 mV noise-floor test. Stored values (motif_member_cooccurrence) are joined for a
consistency check.

Writes pairs.csv and members.csv next to this file. Opens sqlite read-only, .npy with mmap_mode='r'.
"""
import csv, json, os, sqlite3, sys
import numpy as np

ROOT = 'C:/Users/mmebr/Documents/CNN'
sys.path.insert(0, ROOT)
from Working import cross_channel as xc  # noqa: E402  (pure numpy; imports no UI)

HERE = os.path.dirname(os.path.abspath(__file__))
DB = ROOT + '/webui/runtime/20261004-184434/annotations.sqlite'
FAMILIES = ('F-130', 'F-119', 'F-39')
GROUPING = 5
NOISE_MV = 0.1
SCALE = {'V': 1000.0, 'mV': 1.0}


def connect():
    c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c


_arr = {}


def load(path):
    if path not in _arr:
        assert 'M4_aug_concat' not in path
        _arr[path] = np.load(os.path.join(ROOT, path), mmap_mode='r')
    return _arr[path]


RNG = np.random.default_rng(40)
N_NULL = 30


def null_frac(m, s, x, sc_s, rule):
    """Control: the same member window against the SIBLING cut at random OTHER times (>= 60 s away).
    Fraction of those that would also pass the artifact rule (|lag| <= 1 s, |r| >= 0.5)."""
    n, fs = len(x), float(m['fs'])
    arr = load(s['npy_path'])
    N = int(s['n_samples'])
    hits = 0
    strict = 0
    ptp_x = float(np.ptp(x))
    away = int(60 * fs)
    for _ in range(N_NULL):
        while True:
            t0 = int(RNG.integers(0, N - n))
            if abs(t0 - m['start_idx']) >= away:
                break
        y = np.asarray(arr[t0:t0 + n], float) * sc_s
        if y.std() == 0:
            continue
        lag, r, cls = xc.classify_waveforms(x, y, fs=fs, rule=rule)
        hits += cls == xc.ARTIFACT
        ratio = float(np.ptp(y)) / ptp_x if ptp_x > 0 else np.nan
        strict += (cls == xc.ARTIFACT and abs(r) >= 0.9 and 0.5 <= ratio <= 2 and np.ptp(y) >= NOISE_MV)
    return hits / N_NULL, strict / N_NULL


def main():
    c = connect()
    members = [dict(r) for r in c.execute(
        f"""SELECT ga.family_label fam, mm.id, mm.recording_id, mm.start_idx, mm.end_idx,
                   r.source_file, r.channel, r.fs, r.n_samples, r.npy_path, r.units
              FROM grouping_assignments ga JOIN motif_member mm ON mm.id = ga.member_ref
              JOIN recordings r ON r.id = mm.recording_id
             WHERE ga.grouping_id = ? AND ga.family_label IN ({','.join('?' * len(FAMILIES))})""",
        (GROUPING, *FAMILIES))]
    recs = {}
    for r in c.execute("SELECT * FROM recordings"):
        recs.setdefault(r['source_file'], []).append(dict(r))
    stored = {(r['member_id'], r['recording_id']): dict(r) for r in c.execute("SELECT * FROM motif_member_cooccurrence")}
    member_chans = {}
    for m in members:
        member_chans.setdefault(m['fam'], {}).setdefault(m['recording_id'], []).append(m)

    rule = xc.DEFAULT_RULE
    pairs, mrows = [], []
    for m in members:
        sc = SCALE.get(m['units'])
        if sc is None:
            raise SystemExit(f"units undeclared for {m['source_file']}")
        x = np.asarray(load(m['npy_path'])[m['start_idx']:m['end_idx']], float) * sc
        ptp_m = float(np.ptp(x))
        best = None
        for s in recs[m['source_file']]:
            if s['id'] == m['recording_id']:
                continue
            y = np.asarray(load(s['npy_path'])[m['start_idx']:m['end_idx']], float) * SCALE[s['units']]
            n = min(len(x), len(y))
            if n < 4 or x[:n].std() == 0 or y[:n].std() == 0:
                continue
            lag, r, cls = xc.classify_waveforms(x[:n], y[:n], fs=float(m['fs']), rule=rule)
            ptp_s = float(np.ptp(y[:n]))
            nf = null_frac(m, s, x[:n], sc_s=SCALE[s['units']], rule=rule)
            # does the sibling hold a member of the same family within the propagation ceiling? (then W stored the
            # pair on an edge, measured on the union of both spans, instead of a co-occurrence row)
            ceil = rule.propagation_max_lag_s * m['fs']
            sib_member = any(p['start_idx'] - ceil <= m['end_idx'] and m['start_idx'] - ceil <= p['end_idx']
                             for p in member_chans[m['fam']].get(s['id'], []))
            st = stored.get((m['id'], s['id']))
            row = dict(fam=m['fam'], member_id=m['id'], source_file=m['source_file'], member_ch=m['channel'],
                       sib_ch=s['channel'], sib_rec=s['id'], start=m['start_idx'], end=m['end_idx'], n=n,
                       fs=m['fs'], lag_samples=lag, lag_s=lag / m['fs'], r=r, bin=cls,
                       same_instant=(abs(lag / m['fs']) <= rule.artifact_max_lag_s and abs(r) >= rule.min_abs_r),
                       ptp_member_mV=ptp_m, ptp_sib_mV=ptp_s, amp_ratio=ptp_s / ptp_m if ptp_m > 0 else np.nan,
                       sib_clears_floor=ptp_s >= NOISE_MV, member_clears_floor=ptp_m >= NOISE_MV,
                       sib_has_family_member=sib_member,
                       null_same_instant_frac=nf[0], null_strict_frac=nf[1],
                       stored_r=(st['waveform_correlation'] if st else ''),
                       stored_lag=(st['lag'] if st else ''), stored_bin=(st['classification_bin'] if st else ''))
            pairs.append(row)
            if row['same_instant'] and (best is None or abs(r) > abs(best['r'])):
                best = row
        mrows.append(dict(fam=m['fam'], member_id=m['id'], source_file=m['source_file'], channel=m['channel'],
                          start=m['start_idx'], end=m['end_idx'], fs=m['fs'], ptp_mV=ptp_m,
                          flagged=best is not None, best_abs_r=abs(best['r']) if best else '',
                          best_r=best['r'] if best else '', best_sib_ch=best['sib_ch'] if best else '',
                          best_ratio=best['amp_ratio'] if best else '',
                          best_sib_clears=best['sib_clears_floor'] if best else ''))
    for name, rows in (('pairs.csv', pairs), ('members.csv', mrows)):
        with open(os.path.join(HERE, name), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(len(members), 'members', len(pairs), 'pairs')


if __name__ == '__main__':
    main()
