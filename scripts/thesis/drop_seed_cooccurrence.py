"""Do the 372 drop-seed matches in M2_aug happen at the same instant on several channels (common mode)?

Read-only on docs/thesis/data/seed_drop_matches.csv. A match "co-occurs" when another match on a different channel
starts within +-W seconds. Packs are the letter in the channel name (CH1_A1 -> A).
"""
import csv
import collections

P = r"C:\Users\mmebr\Documents\CNN\docs\thesis\data\seed_drop_matches.csv"
rows = [r for r in csv.DictReader(open(P, encoding="utf-8"))]
m = [(float(r["start_s"]), r["channel_name"], r["channel_name"].split("_")[1][0]) for r in rows]
m.sort()
n = len(m)
for W in (50, 300, 1800):
    co = co_x = 0
    clusters = collections.Counter()
    for i, (t, ch, pk) in enumerate(m):
        others = [(t2, ch2, pk2) for (t2, ch2, pk2) in m if ch2 != ch and abs(t2 - t) <= W]
        if others:
            co += 1
            if any(pk2 != pk for (_, _, pk2) in others):
                co_x += 1
        clusters[len({c for (_, c, _) in others}) + 1] += 1
    print(f"W={W:>5}s: {co}/{n} matches have another channel's match within W ({co / n:.1%}); "
          f"{co_x}/{n} with a match in another pack ({co_x / n:.1%}); channels-at-once histogram {dict(sorted(clusters.items()))}")

# chance expectation: shuffle each channel's match times uniformly over 721 h and repeat
import random
random.seed(1)
T = 721 * 3600
chs = collections.Counter(ch for _, ch, _ in m)
for W in (50, 300):
    vals = []
    for _ in range(200):
        sim = sorted((random.uniform(0, T), ch, ch.split("_")[1][0]) for ch, k in chs.items() for _ in range(k))
        co = 0
        j0 = 0
        for i, (t, ch, pk) in enumerate(sim):
            lo = i
            while lo > 0 and t - sim[lo - 1][0] <= W:
                lo -= 1
            hi = i
            while hi + 1 < len(sim) and sim[hi + 1][0] - t <= W:
                hi += 1
            if any(sim[k][1] != ch for k in range(lo, hi + 1) if k != i):
                co += 1
        vals.append(co)
    vals.sort()
    print(f"chance (uniform times, same per-channel counts), W={W}s: mean {sum(vals) / len(vals):.1f}, 95th pct {vals[189]}")
