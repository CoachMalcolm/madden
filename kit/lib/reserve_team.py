"""Add reserve team slots that borrow another team's look, built the way EA built the classic teams.

Differences from the old clone_team (which crashed the game):
  - no coach records (EA's 177 classic teams have none)
  - placed outside the league like the classic teams: CGID 3, DGID 31, LGID 3, TTYP 2
    (the old copy kept the franchise's conference/division, putting a 5th team in a division)
  - borrows stadium, city and art IDs from the source; uniforms are borrowed (same uniform IDs)
  - starts with a copy of the source team's players so it is a full, playable team
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdb import parse, read
from clone import setbits, setstr, fix_crcs, FA_FIELDS


MAX_TEAMS = 299   # tested 10/22: 299 teams play, 300 quit before the coin toss


def _rec(d, t, i):
    return bytearray(d[t.dataoff + i * t.reclen:t.dataoff + (i + 1) * t.reclen])


def _append(d, t, recs):
    assert t.cnt + len(recs) <= t.cap, '%s table is full' % t
    for k, r in enumerate(recs):
        j = t.cnt + k
        d[t.dataoff + j * t.reclen:t.dataoff + (j + 1) * t.reclen] = r
    struct.pack_into('<H', d, t.off + 22, t.cnt + len(recs))


def add_reserve(d, from_tgid, city, nick, abbr, new_tgid=None):
    """d: bytearray of a roster file (changed in place). Returns the new team id."""
    bd = bytes(d); T, _ = parse(bd); F = lambda t: {f[2]: f for f in T[t].fields}
    teams = [read(bd, T['TEAM'], i) for i in range(T['TEAM'].cnt)]
    used = {t['TGID'] for t in teams}
    if len(teams) >= MAX_TEAMS:
        raise SystemExit('Madden 08 quits before the coin toss with more than %d teams. '
                         'Replace an existing reserve slot instead of adding one.' % MAX_TEAMS)
    if new_tgid is None:
        new_tgid = next(x for x in range(268, 400) if x not in used)
    ti = next(i for i, t in enumerate(teams) if t['TGID'] == from_tgid)
    src = teams[ti]
    r = _rec(bd, T['TEAM'], ti); tf = F('TEAM')
    # order right after the classic/Europa/reserve teams (EA's special teams sit at 400+)
    # next order number after the classic/Europa/reserve teams, skipping numbers EA already uses
    # (Pro Bowl and Hall of Fame sit at 400-403; a repeated number is never seen in EA's files)
    max_ord = max(t['TORD'] for t in teams if t['TTYP'] in (2, 7))
    taken = {t['TORD'] for t in teams}
    new_ord = next(x for x in range(max_ord + 1, 1000) if x not in taken)
    vals = dict(TGID=new_tgid, TOID=new_tgid, TORD=new_ord, TCDO=0, TCTX=0, TTYP=2,
                CGID=3, DGID=31, LGID=3,
                TSID=src['TSID'], TGPT=src['TGPT'], TGRP=src['TGRP'], SGID=src['SGID'], CYID=src['CYID'])
    for k, v in vals.items():
        r = setbits(r, tf[k][1], tf[k][3], v)
    for k, s, n in (('TLNA', city, 17), ('TDNA', nick, 16), ('TSNA', abbr, 6), ('TMNC', '', 16)):
        r = setstr(r, tf[k][1], tf[k][3], s[:n])
    _append(d, T['TEAM'], [r])

    # uniforms: same uniform ids as the source (borrowed, not copied art)
    bd = bytes(d); T, _ = parse(bd); uf = F('TUNI')
    recs = [setbits(_rec(bd, T['TUNI'], i), uf['TGID'][1], uf['TGID'][3], new_tgid)
            for i in range(T['TUNI'].cnt) if read(bd, T['TUNI'], i)['TGID'] == from_tgid]
    _append(d, T['TUNI'], recs)

    # players: a copy of the source roster with new ids
    bd = bytes(d); T, _ = parse(bd); P = T['PLAY']; pf = F('PLAY')
    ps = [read(bd, P, i) for i in range(P.cnt)]
    usedp = {p['PGID'] for p in ps} | {p['POID'] for p in ps}
    free = (x for x in range(20000, 30000) if x not in usedp)
    idmap, recs = {}, []
    for i, p in enumerate(ps):
        if p['TGID'] != from_tgid:
            continue
        n = next(free); idmap[p['PGID']] = n; rr = _rec(bd, P, i)
        # contract/commentary/etc. set the way the builder sets created players;
        # exact copies of these fields made the game quit before the coin toss (tested 10/22)
        vals = dict(FA_FIELDS); vals.update(PGID=n, POID=n, TGID=new_tgid)
        for k, v in vals.items():
            rr = setbits(rr, pf[k][1], pf[k][3], v)
        recs.append(rr)
    _append(d, P, recs)

    # depth chart: the source team's chart, pointed at the copies
    bd = bytes(d); T, _ = parse(bd); D = T['DCHT']; df = F('DCHT')
    rows = [read(bd, D, i) for i in range(D.cnt)]
    rows += [dict(x, PGID=idmap[x['PGID']], TGID=new_tgid) for x in rows if x['TGID'] == from_tgid and x['PGID'] in idmap]
    rows.sort(key=lambda x: (x['PGID'], x['PPOS'])); assert len(rows) <= D.cap
    blank = bytearray(D.reclen)
    for i, x in enumerate(rows):
        rec = bytearray(blank)
        for k in ('PGID', 'TGID', 'PPOS', 'ddep'):
            rec = setbits(rec, df[k][1], df[k][3], x[k])
        d[D.dataoff + i * D.reclen:D.dataoff + (i + 1) * D.reclen] = rec
    struct.pack_into('<H', d, D.off + 22, len(rows))
    fix_crcs(d)
    return new_tgid, len(recs)


if __name__ == '__main__':
    # python reserve_team.py base.ros out.ros FROM_TGID "City" "Nickname" ABBR [FROM_TGID "City" "Nick" ABBR ...]
    src, out, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    d = bytearray(open(src, 'rb').read())
    for k in range(0, len(rest), 4):
        tg, n = add_reserve(d, int(rest[k]), rest[k + 1], rest[k + 2], rest[k + 3])
        print('added team %d: %s %s (%d players)' % (tg, rest[k + 1], rest[k + 2], n))
    open(out, 'wb').write(d)
