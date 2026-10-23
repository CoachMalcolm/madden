"""Build a Madden 08 game roster from sheet rows.
rows: [first, last, jersey, pos, clone_label, madden_team_full_name]
- Base: stock 2007.ros (Madden 08). Clones copied from any source roster (same PLAY schema).
- Each created player joins the named team; never cut. If a team goes over 55, the lowest-rated
  NFL (non-created) players at that team are released to free agency.
- Team names can be changed. Depth charts: created players first at their position (best OVR first),
  then the team's existing NFL depth.
"""
import sys, json, struct, collections
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from tdb import parse, read
from clone import setbits, setstr, fix_crcs, FA_FIELDS
import os as _os
_KIT = _os.environ.get('MADDEN_KIT') or _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
R = _os.path.join(_KIT, 'rosters', 'sources') + _os.sep
SRC = {k: R + k for k in ['1995.ros','1996.ros','2003.ros','2004.ros','2005.ros','2006.ros','2007.ros','2020ROJOROSTER V22.ros','2026JINXROSTER V0.40.ros']}
SRC['GHT.ros'] = R + 'GHT.ros'
POS = 'QB HB FB WR TE LT LG C RG RT LE RE DT LOLB MLB ROLB CB FS SS K P'.split()
FA = 1009

def rec_of(d, t, i): return bytearray(d[t.dataoff+i*t.reclen:t.dataoff+(i+1)*t.reclen])

def build(rows, out_path, renames=None, base='2007.ros', log=print, depth=True):
    greats = {e['label']: e for e in json.load(open(_os.path.join(_KIT, 'data', 'greats_v3.json')))}
    d = bytearray(open(SRC[base], 'rb').read())
    T, _ = parse(bytes(d)); P, TM, D = T['PLAY'], T['TEAM'], T['DCHT']
    PF = {f[2]: f for f in P.fields}; TF = {f[2]: f for f in TM.fields}; DF = {f[2]: f for f in D.fields}
    teams = {}
    for i in range(TM.cnt):
        r = read(bytes(d), TM, i); teams[(r['TLNA'] + ' ' + r['TDNA']).strip()] = (r['TGID'], i)
    players = [read(bytes(d), P, i) for i in range(P.cnt)]
    used = {p['PGID'] for p in players} | {p['POID'] for p in players}
    free = (x for x in range(30000, 32700) if x not in used)
    srcdb = {}
    def src(f):
        if f not in srcdb:
            sd = open(SRC[f], 'rb').read(); st, _ = parse(sd); srcdb[f] = (sd, st['PLAY'])
        return srcdb[f]
    created = []          # (pgid, tgid, pos, ovr, name)
    problems = []
    newrecs = []
    for first, last, jersey, pos, label, team in rows:
        e = greats.get(label)
        if not e: problems.append('No clone match: %s %s -> %r' % (first, last, label)); continue
        if team not in teams: problems.append('Unknown team %r for %s %s' % (team, first, last)); continue
        if e['pos'] != pos: problems.append('Position mismatch %s %s: %s vs clone %s' % (first, last, pos, e['pos'])); continue
        sd, sp = src(e['src'])
        rec = rec_of(sd, sp, e['idx'])
        tgid = teams[team][0]; nid = next(free)
        vals = dict(FA_FIELDS); vals.update(PGID=nid, POID=nid, TGID=tgid)
        vals['PJEN'] = int(jersey) if str(jersey).strip().isdigit() else read(sd, sp, e['idx'])['PJEN']
        for n, v in vals.items():
            ty, bo, _, bc = PF[n]; rec = setbits(rec, bo, bc, v)
        rec = setstr(rec, PF['PFNA'][1], PF['PFNA'][3], first.strip()[:10])
        rec = setstr(rec, PF['PLNA'][1], PF['PLNA'][3], last.strip()[:12])
        newrecs.append(rec)
        created.append((nid, tgid, e['pos'], e['ovr'], '%s %s' % (first.strip(), last.strip()), e.get('KR', 0)))
    # append created players
    assert P.cnt + len(newrecs) <= P.cap
    for k, rec in enumerate(newrecs):
        j = P.cnt + k; d[P.dataoff + j*P.reclen: P.dataoff + (j+1)*P.reclen] = rec
    struct.pack_into('<H', d, P.off + 22, P.cnt + len(newrecs))
    T, _ = parse(bytes(d)); P = T['PLAY']
    allp = [read(bytes(d), P, i) for i in range(P.cnt)]
    newids = {c[0] for c in created}
    # roster cap 55: release lowest NFL players
    touched = sorted({c[1] for c in created})
    released = collections.defaultdict(list)
    for tg in touched:
        mine = [(i, p) for i, p in enumerate(allp) if p['TGID'] == tg]
        over = len(mine) - 55
        if over > 0:
            nfl = sorted([(p['POVR'], i, p) for i, p in mine if p['PGID'] not in newids])
            for ovr, i, p in nfl[:over]:
                rec = rec_of(bytes(d), P, i); ty, bo, _, bc = PF['TGID']; rec = setbits(rec, bo, bc, FA)
                d[P.dataoff + i*P.reclen: P.dataoff + (i+1)*P.reclen] = rec
                released[tg].append('%s %s (%s %d)' % (p['PFNA'], p['PLNA'], POS[p['PPOS']], ovr))
    # depth charts
    T, _ = parse(bytes(d)); P, D = T['PLAY'], T['DCHT']
    if depth:
        # PGIDs are not unique in every mod's roster, so match on (player id, team) pairs.
        onteam = {(r['PGID'], r['TGID']) for r in (read(bytes(d), P, i) for i in range(P.cnt))}
        dc = [read(bytes(d), D, i) for i in range(D.cnt)]
        keep = [r for r in dc if r['TGID'] not in touched]
        old = collections.defaultdict(list)
        for r in dc:
            if r['TGID'] in touched and (r['PGID'], r['TGID']) in onteam:
                old[(r['TGID'], r['PPOS'])].append((r['ddep'], r['PGID']))
        newdc = []
        for tg in touched:
            mine = sorted([c for c in created if c[1] == tg], key=lambda c: -c[3])
            for slot in range(26):
                if slot <= 20: first = [c[0] for c in mine if POS.index(c[2]) == slot]
                elif slot in (21, 22):  # KR / PR: best kick-return created players
                    first = [c[0] for c in sorted(mine, key=lambda c: -c[5]) if c[2] in ('HB','WR','CB','FS','SS')][:2]
                elif slot == 23: first = [c[0] for c in mine if c[2] == 'K']
                elif slot == 25: first = [c[0] for c in mine if c[2] == 'HB']
                else: first = []
                rest = [pg for _, pg in sorted(old[(tg, slot)]) if pg not in first]
                order = (first + rest)[:max(len(rest), len(first), 1) + len(first)]
                for depth, pg in enumerate(order[:31]):
                    newdc.append({'PGID': pg, 'TGID': tg, 'PPOS': slot, 'ddep': depth})
        rows_dc = keep + newdc
        rows_dc.sort(key=lambda r: (r['PGID'], r['PPOS']))
        assert len(rows_dc) <= D.cap
        blank = bytearray(D.reclen)
        for i, r in enumerate(rows_dc):
            rec = bytearray(blank)
            for n in ('PGID', 'TGID', 'PPOS', 'ddep'):
                ty, bo, _, bc = DF[n]; rec = setbits(rec, bo, bc, r[n])
            d[D.dataoff + i*D.reclen: D.dataoff + (i+1)*D.reclen] = rec
        for i in range(len(rows_dc), D.cnt):
            d[D.dataoff + i*D.reclen: D.dataoff + (i+1)*D.reclen] = blank
        struct.pack_into('<H', d, D.off + 22, len(rows_dc))
    # team renames
    for full, (city, nick, abbr) in (renames or {}).items():
        tg, ti = teams[full]
        T, _ = parse(bytes(d)); TM = T['TEAM']
        rec = rec_of(bytes(d), TM, ti)
        rec = setstr(rec, TF['TLNA'][1], TF['TLNA'][3], city[:17])
        rec = setstr(rec, TF['TDNA'][1], TF['TDNA'][3], nick[:16])
        rec = setstr(rec, TF['TSNA'][1], TF['TSNA'][3], abbr[:6])
        rec = setstr(rec, TF['TMNC'][1], TF['TMNC'][3], nick[:16])
        d[TM.dataoff + ti*TM.reclen: TM.dataoff + (ti+1)*TM.reclen] = rec
    fix_crcs(d)
    open(out_path, 'wb').write(d)
    return created, released, problems

if __name__ == '__main__':
    rows = json.load(open(sys.argv[1]))
    created, released, problems = build(rows, sys.argv[2], renames={
        'New York Giants': ('Dodge Field', 'All-Stars', 'DFA'),
        'New York Jets': ('Madison', 'Dodgers', 'MAD')})
    print('created', len(created)); print('released', {k: len(v) for k, v in released.items()}); print('problems', problems)
