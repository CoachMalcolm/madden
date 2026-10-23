"""Clone an existing team into a brand-new team slot: team record, uniforms, coaches, players, depth chart."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdb import parse, read
from clone import setbits, setstr, fix_crcs

def _rec(d, t, i): return bytearray(d[t.dataoff+i*t.reclen:t.dataoff+(i+1)*t.reclen])
def _append(d, t, recs):
    assert t.cnt + len(recs) <= t.cap, 'table full'
    for k, r in enumerate(recs):
        j = t.cnt + k; d[t.dataoff+j*t.reclen:t.dataoff+(j+1)*t.reclen] = r
    struct.pack_into('<H', d, t.off + 22, t.cnt + len(recs))

def clone_team(src, out, from_tgid, city, nick, new_tgid=None, uni_from=None):
    d = bytearray(open(src, 'rb').read())
    T, _ = parse(bytes(d)); F = lambda t: {f[2]: f for f in T[t].fields}
    teams = [read(bytes(d), T['TEAM'], i) for i in range(T['TEAM'].cnt)]
    used = {t['TGID'] for t in teams}
    if new_tgid is None: new_tgid = next(x for x in range(268, 1000) if x not in used)
    # team record
    ti = next(i for i, t in enumerate(teams) if t['TGID'] == from_tgid)
    r = _rec(bytes(d), T['TEAM'], ti); tf = F('TEAM')
    max_ord = max(t['TORD'] for t in teams if t['TORD'] < 1000)
    # same pattern the mod's classic teams use: own ID and order, art IDs (TSID/TGPT/TGRP) point at the source franchise
    for k, v in (('TGID', new_tgid), ('TOID', new_tgid), ('TORD', max_ord + 1), ('TCDO', 0), ('TCTX', 0), ('TTYP', 2),
                 ('TSID', teams[ti]['TSID']), ('TGPT', teams[ti]['TGPT']), ('TGRP', teams[ti]['TGRP'])):
        r = setbits(r, tf[k][1], tf[k][3], v)
    r = setstr(r, tf['TLNA'][1], tf['TLNA'][3], city[:17]); r = setstr(r, tf['TDNA'][1], tf['TDNA'][3], nick[:16])
    _append(d, T['TEAM'], [r])
    # uniforms and coaches
    for tab in ('TUNI', 'COCH'):
        T, _ = parse(bytes(d)); f = F(tab); src_tg = (uni_from or from_tgid) if tab == 'TUNI' else from_tgid
        recs = [setbits(_rec(bytes(d), T[tab], i), f['TGID'][1], f['TGID'][3], new_tgid)
                for i in range(T[tab].cnt) if read(bytes(d), T[tab], i)['TGID'] == src_tg]
        _append(d, T[tab], recs)
    # players
    T, _ = parse(bytes(d)); P = T['PLAY']; pf = F('PLAY')
    ps = [read(bytes(d), P, i) for i in range(P.cnt)]
    usedp = {p['PGID'] for p in ps} | {p['POID'] for p in ps}
    free = (x for x in range(1, 32700) if x not in usedp)
    idmap, recs = {}, []
    for i, p in enumerate(ps):
        if p['TGID'] != from_tgid: continue
        n = next(free); idmap[p['PGID']] = n; r = _rec(bytes(d), P, i)
        for k, v in (('PGID', n), ('POID', n), ('TGID', new_tgid)): r = setbits(r, pf[k][1], pf[k][3], v)
        recs.append(r)
    _append(d, P, recs)
    # depth chart (re-sorted by player id, then position)
    T, _ = parse(bytes(d)); D = T['DCHT']; df = F('DCHT')
    rows = [read(bytes(d), D, i) for i in range(D.cnt)]
    rows += [dict(r, PGID=idmap[r['PGID']], TGID=new_tgid) for r in rows if r['TGID'] == from_tgid and r['PGID'] in idmap]
    rows.sort(key=lambda r: (r['PGID'], r['PPOS'])); assert len(rows) <= D.cap
    blank = bytearray(D.reclen)
    for i, r in enumerate(rows):
        rec = bytearray(blank)
        for k in ('PGID', 'TGID', 'PPOS', 'ddep'): rec = setbits(rec, df[k][1], df[k][3], r[k])
        d[D.dataoff+i*D.reclen:D.dataoff+(i+1)*D.reclen] = rec
    struct.pack_into('<H', d, D.off + 22, len(rows))
    fix_crcs(d); open(out, 'wb').write(d)
    return new_tgid, len(recs)
