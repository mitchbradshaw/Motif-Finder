"""A minimal QR code encoder (byte mode, error correction M, versions 1-6) that writes an SVG, so the demo hub can
show "scan to join" with no new dependency. ISO/IEC 18004; checked against phone scanners by the URL it carries."""
from __future__ import annotations

# (total codewords, EC codewords per block, number of blocks) for error correction level M
_M = {1: (26, 10, 1), 2: (44, 16, 1), 3: (70, 26, 1), 4: (100, 18, 2), 5: (134, 24, 2), 6: (172, 16, 4)}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}

# GF(256), primitive polynomial x^8 + x^4 + x^3 + x^2 + 1
_EXP = [0] * 512
_LOG = [0] * 256
_v = 1
for _i in range(255):
    _EXP[_i] = _v
    _LOG[_v] = _i
    _v <<= 1
    if _v & 0x100:
        _v ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gmul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _generator(n):
    g = [1]
    for i in range(n):
        g = [a ^ b for a, b in zip(g + [0], [0] + [_gmul(c, _EXP[i]) for c in g])]
    return g


def _rs(data, n):
    g = _generator(n)
    rem = [0] * n
    for d in data:
        f = d ^ rem[0]
        rem = rem[1:] + [0]
        if f:
            for i in range(n):
                rem[i] ^= _gmul(g[i + 1], f)
    return rem


def _codewords(text: str):
    raw = text.encode("utf-8")
    for ver in range(1, 7):
        total, ec, blocks = _M[ver]
        data_cw = total - ec * blocks
        if 4 + 8 + 8 * len(raw) <= 8 * data_cw:
            break
    else:
        raise ValueError("text too long for this encoder (versions 1-6)")
    bits = [0, 1, 0, 0] + [int(b) for b in f"{len(raw):08b}"]
    for byte in raw:
        bits += [int(b) for b in f"{byte:08b}"]
    bits += [0] * min(4, 8 * data_cw - len(bits))
    bits += [0] * (-len(bits) % 8)
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    n0 = len(data)
    while len(data) < data_cw:
        data.append(pad[(len(data) - n0) % 2])
    per = data_cw // blocks
    blks = [data[i * per:(i + 1) * per] for i in range(blocks)]
    ecs = [_rs(b, ec) for b in blks]
    out = [b[i] for i in range(per) for b in blks] + [e[i] for i in range(ec) for e in ecs]
    return ver, out


def _matrix(ver, codewords):
    n = 17 + 4 * ver
    m = [[None] * n for _ in range(n)]

    def finder(r, c):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = r + dr, c + dc
                if 0 <= rr < n and 0 <= cc < n:
                    on = 0 <= dr <= 6 and 0 <= dc <= 6 and (dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4))
                    m[rr][cc] = 1 if on else 0
    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)
    for i in range(8, n - 8):
        m[6][i] = m[i][6] = 1 if i % 2 == 0 else 0
    pos = _ALIGN[ver]
    for r in pos:
        for c in pos:
            if m[r][c] is not None:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    m[r + dr][c + dc] = 1 if max(abs(dr), abs(dc)) != 1 else 0
    m[4 * ver + 9][8] = 1
    reserved = [[v is not None for v in row] for row in m]
    for i in range(9):          # the format areas
        if m[8][i] is None:
            reserved[8][i] = True
        if m[i][8] is None:
            reserved[i][8] = True
    for i in range(8):
        reserved[8][n - 1 - i] = True
        reserved[n - 1 - i][8] = True
    bits = [int(b) for cw in codewords for b in f"{cw:08b}"]
    k = 0
    up = True
    c = n - 1
    while c > 0:
        if c == 6:
            c -= 1
        rows = range(n - 1, -1, -1) if up else range(n)
        for r in rows:
            for cc in (c, c - 1):
                if not reserved[r][cc]:
                    m[r][cc] = bits[k] if k < len(bits) else 0
                    k += 1
        up = not up
        c -= 2
    return m, reserved


_MASKS = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0,
          lambda r, c: (r + c) % 3 == 0, lambda r, c: (r // 2 + c // 3) % 2 == 0,
          lambda r, c: (r * c) % 2 + (r * c) % 3 == 0, lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
          lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0]


def _format_bits(mask):
    d = (0b00 << 3) | mask        # level M = 00
    v = d << 10
    for i in range(14, 9, -1):
        if v & (1 << i):
            v ^= 0x537 << (i - 10)
    return ((d << 10) | v) ^ 0x5412


def _place_format(m, mask):
    n = len(m)
    f = _format_bits(mask)
    bit = [(f >> i) & 1 for i in range(15)]
    # first copy, around the top-left finder (m[row][col]; the order of ISO 18004 fig. 25)
    for i in range(6):
        m[i][8] = bit[i]
    m[7][8] = bit[6]
    m[8][8] = bit[7]
    m[8][7] = bit[8]
    for i in range(9, 15):
        m[8][14 - i] = bit[i]
    # second copy: row 8 under the top-right finder, column 8 beside the bottom-left one
    for i in range(8):
        m[8][n - 1 - i] = bit[i]
    for i in range(8, 15):
        m[n - 15 + i][8] = bit[i]
    m[n - 8][8] = 1                # the dark module


def _penalty(m):
    n = len(m)
    p = 0
    for line in [row for row in m] + [[m[r][c] for r in range(n)] for c in range(n)]:
        run, prev = 0, None
        for v in line:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    p += 3 + run - 5
                run, prev = 1, v
        if run >= 5:
            p += 3 + run - 5
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r + 1][c] == m[r][c + 1] == m[r + 1][c + 1]:
                p += 3
    dark = sum(sum(row) for row in m)
    p += 10 * (abs(dark * 20 - n * n * 10) // (n * n))
    return p


def qr_matrix(text: str):
    ver, cws = _codewords(text)
    base, reserved = _matrix(ver, cws)
    best = None
    for k, fn in enumerate(_MASKS):
        m = [row[:] for row in base]
        for r in range(len(m)):
            for c in range(len(m)):
                if not reserved[r][c] and fn(r, c):
                    m[r][c] ^= 1
        _place_format(m, k)
        sc = _penalty(m)
        if best is None or sc < best[0]:
            best = (sc, m)
    return best[1]


def qr_svg(text: str, *, module=8, border=4, dark="#111827", light="#ffffff") -> str:
    m = qr_matrix(text)
    n = len(m)
    size = (n + 2 * border) * module
    rects = [f'<rect x="{(c + border) * module}" y="{(r + border) * module}" width="{module}" height="{module}"/>'
             for r in range(n) for c in range(n) if m[r][c]]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
            f'shape-rendering="crispEdges"><rect width="100%" height="100%" fill="{light}"/>'
            f'<g fill="{dark}">{"".join(rects)}</g></svg>')
