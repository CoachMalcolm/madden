"""Master Madden List v6 roster builder.

Reads the whole v6 workbook (File > Download > Microsoft Excel .xlsx) and builds a Madden 08 .ros:

    python madden_build_v6.py "input/Malcolm's Master Madden List v6.xlsx" SQUADS1

- Build Your Squads: each named squad replaces the NFL team picked under "Replaces".
  The game shows the squad's City and Nickname (blank = the team's city and the squad name).
- Players: every tick box in P-U puts one copy of that player on that squad.
  (One-squad-per-row layout: Build Your Squads has a Number of squads cell and one row per squad,
  and Players column "Squads" lists each player's squads; both layouts are read.)
  Only players whose Clone check says OK are built.
- Open spots: for each position below the Settings minimum, the best player of the replaced
  team at that position stays. Everyone else on a replaced NFL team goes to free agency;
  on a reserve team (Broncos A, Raiders B ...) they are deleted, since they are only copies.
- Skin tone (Light / Medium / Dark) is applied. Ratings over the OP limit are listed (OP tag).
"""
import argparse, collections, json, os, re, shutil, struct, sys, zlib

KIT = os.environ.get('MADDEN_KIT') or os.path.dirname(os.path.abspath(__file__))   # MADDEN_KIT: set by the Windows program
sys.path.insert(0, os.path.join(KIT, 'lib'))
import build_showdown as B
from sanitize import sanitize
from clone import verify, setbits, fix_crcs
from tdb import parse, read
from xlsx import Workbook, cell

POS = B.POS
FA = B.FA
SQUAD_COLS = 'CEGIKM'                      # Build Your Squads: one squad per two columns
TICK_FIRST = 15                            # Players column P (0-based 15) = squad 1 ... U = squad 6
SKIN = {'light': 0, 'medium': 1, 'dark': 2}
RESERVE_TGIDS = range(268, 400)            # reserve slots made by lib/reserve_team.py
RATING_KEYS = 'SPD ACC AGI STR AWR CTH CAR BTK JMP THP THA PBK RBK TAK KPW KAC KR STA INJ TGH'.split()


def clean(s):
    return re.sub(r'\s+', ' ', str(s if s is not None else '')).strip()


def num(v, default):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def read_workbook(path):
    wb = Workbook(path)
    st, sq, pl = wb.sheet('Settings'), wb.sheet('Build Your Squads'), wb.sheet('Players')
    settings = dict(cap=num(cell(st, 'B5'), 127), op=num(cell(st, 'B6'), 99), per_squad=num(cell(st, 'B7'), 55))
    need = {}
    for r in range(5, 26):
        p = clean(cell(st, 'G%d' % r))
        if p in POS:
            need[p] = num(cell(st, 'H%d' % r), 0)
    notes = []
    rows_layout = find_row_layout(sq)
    if rows_layout:
        # Newer layout: one squad per row, "Number of squads" at the top (tested in the TEST copy).
        hdr, cols, count = rows_layout
        # squad rows are the rows below the header whose # column (left of Squad name) holds 1..count
        row_of = {}
        for (r, c), v in sq.items():
            if r > hdr and c == cols['name'] - 1 and num(v, 0) >= 1 and num(v, 0) <= count:
                row_of.setdefault(num(v, 0), r)
        squads = []
        for k in range(1, count + 1):
            r = row_of.get(k)
            g = lambda key: clean(sq.get((r, cols[key]), '')) if (r is not None and key in cols) else ''
            squads.append(dict(slot=k, name=g('name'), replaces=g('replaces'), city=g('city'), nick=g('nick')))
    else:
        # Original layout: six squads side by side, rows found by their labels in column A.
        labels = {}
        for (r, c), v in sq.items():
            if c == 0 and isinstance(v, str):
                low = clean(v).lower()
                for key, start in (('name', 'squad name'), ('replaces', 'replaces'), ('city', 'game city'), ('nick', 'game nickname')):
                    if low.startswith(start) and key not in labels:
                        labels[key] = r + 1
        missing = [k for k in ('name', 'replaces') if k not in labels]
        if missing:
            sys.exit('Build Your Squads: could not find the "Squad name" / "Replaces" rows in column A.')
        get = lambda c, key: clean(cell(sq, '%s%d' % (c, labels[key]))) if key in labels else ''
        squads = []
        for k, c in enumerate(SQUAD_COLS):
            squads.append(dict(slot=k + 1, name=get(c, 'name'), replaces=get(c, 'replaces'),
                               city=get(c, 'city'), nick=get(c, 'nick')))
    # Headings: row 1 in older workbooks, row 2 once row 1 holds the Show toggles. Find the row with "First Name".
    hrow = min((r for (r, c), v in pl.items() if r < 5 and isinstance(v, str) and clean(v).lower().startswith('first name')), default=0)
    head = {clean(v).lower(): col for (r, col), v in pl.items() if r == hrow}

    def col(prefix):
        for h, c in head.items():
            if h.startswith(prefix):
                return c
        sys.exit('Players tab is missing the "%s" column.' % prefix)
    C = dict(first=col('first'), last=col('last'), season=col('season'), jersey=col('#'), pos=col('position'),
             clone=col('nfl all time great clone'), check=col('clone check'), skin=col('skin tone'))
    if rows_layout:
        C['squads'] = col('squads')
        slot_of = {sqd['name']: sqd['slot'] for sqd in squads if sqd['name']}
        unknown = {}
    nrows = max(r for r, _ in pl) + 1
    players = []
    for r in range(hrow + 1, nrows):
        g = lambda k: clean(pl.get((r, C[k]), ''))
        if not (g('first') or g('last')):
            continue
        if rows_layout:
            ticks = []
            for nm in [clean(x) for x in str(pl.get((r, C['squads']), '') or '').split(',')]:
                if not nm:
                    continue
                if nm in slot_of:
                    if slot_of[nm] not in ticks:
                        ticks.append(slot_of[nm])
                else:
                    unknown.setdefault(nm, []).append(r + 1)
        else:
            ticks = [k + 1 for k in range(6) if pl.get((r, TICK_FIRST + k)) is True]
        players.append(dict(line=r + 1, first=g('first'), last=g('last'), jersey=g('jersey'), pos=g('pos'),
                            clone=g('clone'), check=g('check'), skin=g('skin').lower(), ticks=ticks))
    if rows_layout:
        for nm, lines in unknown.items():
            notes.append('%d player(s) are on squad "%s", which is not a squad on Build Your Squads '
                         '(misspelled, renamed, or past the Number of squads); left out. Players rows: %s'
                         % (len(lines), nm, ', '.join(map(str, lines[:12])) + (' ...' if len(lines) > 12 else '')))
    settings['allow'] = read_allow(sq)
    custom = read_custom(wb, notes, settings['cap'])
    for p in players:
        c = custom.get((p['first'].lower(), p['last'].lower(), p['pos']))
        if c:
            p['custom'] = c
    return settings, need, squads, players, notes


def read_allow(sq):
    """Build Your Squads switches: a tick box just left of "Allow B ..." / "Allow C ...". Missing = allowed."""
    allow = {'B': True, 'C': True}
    for (r, c), v in sq.items():
        m = re.match(r'allow\s+([bc])\b', clean(v).lower()) if isinstance(v, str) else None
        if m and c > 0:
            box = sq.get((r, c - 1), True)
            allow[m.group(1).upper()] = box is True or str(box).strip().upper() == 'TRUE'
    return allow


CUSTOM_TAB = 'Custom Players'
CUSTOM_FIELDS = {'height': 'HGT', 'weight': 'WGT', 'age': 'AGE'}


CUSTOM_ERRORS = []
CP_NAMES = json.load(open(os.path.join(KIT, 'data', 'custom_players.json')))['names']
BODY_LIMITS = {'HGT': (60, 90, 'Height (inches)'), 'WGT': (160, 400, 'Weight (lbs)'), 'AGE': (18, 50, 'Age')}


def read_custom(wb, notes, cap=127):
    """Custom Players tab (optional): one row per player whose ratings were set by hand.
    Type B = edited clone (his clone with some numbers changed); type C = from scratch (no clone).
    Blank cells keep the default (the clone's number for B, the average player at that position for C)."""
    if CUSTOM_TAB not in wb.sheets:
        return {}
    cp = wb.sheet(CUSTOM_TAB)
    # the header row is the one with First and Last (row 2 when the Show dropdown sits above it)
    hrow = next((r for r in sorted({r for r, _ in cp}) if any(clean(cp.get((r, c), '')).lower() == 'first' for c in range(6))), 0)
    head = {c: clean(v) for (r, c), v in cp.items() if r == hrow}
    col = {}
    for c, h in head.items():
        low = h.lower()
        m = re.search(r'\(([A-Z]{2,3})\)\s*$', h)
        if m:
            col[c] = m.group(1)
        elif low.startswith('first'):
            col[c] = 'first'
        elif low.startswith('last'):
            col[c] = 'last'
        elif low.startswith('position'):
            col[c] = 'pos'
        elif low.startswith('type'):
            col[c] = 'type'
        else:
            for word, key in CUSTOM_FIELDS.items():
                if low.startswith(word):
                    col[c] = key
    out = {}
    nrows = max((r for r, _ in cp), default=0) + 1
    for r in range(hrow + 1, nrows):
        row = {key: cp.get((r, c), '') for c, key in col.items()}
        first, last, pos = clean(row.get('first')), clean(row.get('last')), clean(row.get('pos'))
        ty = clean(row.get('type')).lower()
        # B = edited clone, C = from scratch (older saves: "A: Start from clone" = edited, "B: From scratch")
        kind = 'C' if 'scratch' in ty else 'B' if ('edit' in ty or 'clone' in ty) else ''
        if not (first or last) or not kind:
            continue
        vals = {}
        for key, v in row.items():
            if key in ('first', 'last', 'pos', 'type') or clean(v) == '':
                continue
            n = num(v, None)
            if n is None:
                notes.append('Custom Players row %d (%s %s): "%s" is not a number for %s; using the default.' % (r + 1, first, last, v, key))
                continue
            lo, hi, label = BODY_LIMITS.get(key, (0, min(127, int(cap)), CP_NAMES.get(key, key)))
            if n != int(n) or not lo <= n <= hi:
                CUSTOM_ERRORS.append('Custom Players row %d (%s %s): %s is %s; it must be a whole number from %d to %d%s.'
                                     % (r + 1, first, last, label, clean(v), lo, hi,
                                        '' if key in BODY_LIMITS else ' (ratings cap on Settings)'))
                continue
            vals[key] = n
        out[(first.lower(), last.lower(), pos)] = dict(type=kind, vals=vals, line=r + 1)
    return out


def find_row_layout(sq):
    """One-squad-per-row layout: a header row holding "Squad name" and "Replaces" side by side,
    and a "Number of squads" cell. Returns (header row, {key: column}, count) or None."""
    hdr, cols = None, {}
    for (r, c), v in sorted(sq.items()):
        if isinstance(v, str) and clean(v).lower() == 'squad name' and c > 0 and \
                clean(sq.get((r, c + 1), '')).lower() == 'replaces':
            hdr = r
            for (r2, c2), v2 in sq.items():
                if r2 == r and isinstance(v2, str):
                    low = clean(v2).lower()
                    for key, start in (('name', 'squad name'), ('replaces', 'replaces'), ('city', 'game city'), ('nick', 'game nickname')):
                        if low.startswith(start):
                            cols[key] = c2
            break
    if hdr is None:
        return None
    count = None
    for (r, c), v in sq.items():
        if isinstance(v, str) and clean(v).lower().startswith('number of squads'):
            count = num(sq.get((r, c + 1)), None)
    if not count or count < 1:
        sys.exit('Build Your Squads: set the Number of squads (1 to 32) at the top of the tab.')
    return hdr, cols, int(count)


CP = json.load(open(os.path.join(KIT, 'data', 'custom_players.json')))
RAW = {'SPD': 'PSPD', 'ACC': 'PACC', 'AGI': 'PAGI', 'STR': 'PSTR', 'AWR': 'PAWR', 'CTH': 'PCTH', 'CAR': 'PCAR',
       'BTK': 'PBTK', 'JMP': 'PJMP', 'THP': 'PTHP', 'THA': 'PTHA', 'PBK': 'PPBK', 'RBK': 'PRBK', 'TAK': 'PTAK',
       'KPW': 'PKPR', 'KAC': 'PKAC', 'KR': 'PKRT', 'STA': 'PSTA', 'INJ': 'PINJ', 'TGH': 'PTGH',
       'HGT': 'PHGT', 'WGT': 'PWGT', 'AGE': 'PAGE'}


def custom_ovr(pos, e, capped=True):
    """EA's overall formula for the position (fitted on EA's own rosters), capped 0-99."""
    w = CP['model'][pos]
    v = sum(e[k] * w[i] for i, k in enumerate(CP['keys'])) + w[-1]
    return max(0, min(99, int(round(v)))) if capped else v


def custom_entry(e, cu, pos, cap):
    """The clone (A) or the average-player template (B) with the saved numbers on top."""
    out = dict(e)
    if cu['type'] == 'C':
        out.update(CP['avg'][pos])               # every number starts at the position's average
    for k, v in cu['vals'].items():
        if k in RAW:
            out[k] = max(0, min(cap if k in CP['keys'] else 400, int(v)))
    if cu['type'] == 'C':
        out['ovr'] = custom_ovr(pos, out)
    elif any(k in CP['keys'] for k in cu['vals']):
        # A: keep the clone's own overall and move it by however much the changes move EA's formula,
        # so a clone from a community roster (rated a little differently) isn't re-rated from scratch.
        out['ovr'] = max(0, min(99, int(round(e['ovr'] + custom_ovr(pos, out, False) - custom_ovr(pos, e, False)))))
    out['custom'] = cu['type']
    return out


def apply_custom(d, P2, PF2, idx, created, mine):
    """Write custom ratings, height, weight, age and the new overall into each custom player's record."""
    said = []
    for (pgid, tg, pos, ovr, name, kr), (p, e) in zip(created, mine):
        if not e.get('custom'):
            continue
        i = idx[pgid]; rec = B.rec_of(bytes(d), P2, i)
        vals = {RAW[k]: e[k] for k in RAW if k in e}
        vals['PWGT'] = max(0, e['WGT'] - 160)      # stored as pounds over 160
        vals['POVR'] = e['ovr']
        for f, v in vals.items():
            ty, bo, _, bc = PF2[f]; rec = setbits(rec, bo, bc, min(int(v), (1 << bc) - 1))
        d[P2.dataoff + i * P2.reclen:P2.dataoff + (i + 1) * P2.reclen] = rec
        said.append('%s (%s): %s, OVR %d' % (name, pos, 'C, from scratch' if e['custom'] == 'C' else 'B, edited clone of %s' % p['clone'], e['ovr']))
    return said


def op_list(e, op):
    out = []
    if e['ovr'] > op:
        out.append('OVR %d' % e['ovr'])
    for k in RATING_KEYS:
        v = e.get(k, 0)
        if v > op and not (e['name'] == 'Devin Hester' and k == 'SPD' and v == 100):
            out.append('%s %d' % (k, v))
    return out


def face_tables(roster):
    """Face id -> skin tone it belongs to, and the most used faces of each tone, from a roster."""
    T, _ = parse(roster); P = T['PLAY']
    by = collections.defaultdict(collections.Counter)
    for i in range(P.cnt):
        r = read(roster, P, i); by[r['PFEx']][r['PSKI']] += 1
    face_skin, pool = {}, collections.defaultdict(list)
    for face, c in by.items():
        tone, n = c.most_common(1)[0]
        face_skin[face] = tone
        if n / sum(c.values()) >= 0.95:
            pool[tone].append((n, face))
    return face_skin, {t: [f for n, f in sorted(v, reverse=True)[:6]] for t, v in pool.items()}


def madden_rosters_folder():
    """Documents\\Madden NFL 08\\Rosters on this PC (follows a moved/OneDrive Documents folder), or None."""
    docs = None
    if os.name == 'nt':
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                docs = buf.value
        except Exception:
            docs = None
    for d in [docs, os.path.join(os.path.expanduser('~'), 'Documents')]:
        if d:
            f = os.path.join(d, 'Madden NFL 08', 'Rosters')
            if os.path.isdir(f):
                return f
    return None


def fill_depth(path, tgids):
    """Give every depth-chart slot of the touched teams at least one player.
    Slots 0-20 are the positions; 21 KR, 22 PR, 23 kickoff, 24 long snapper, 25 third-down back."""
    d = bytearray(open(path, 'rb').read()); T, _ = parse(bytes(d)); P, D = T['PLAY'], T['DCHT']
    DF = {f[2]: f for f in D.fields}
    players = [read(bytes(d), P, i) for i in range(P.cnt)]
    rows = [read(bytes(d), D, i) for i in range(D.cnt)]
    added = []
    for tg in tgids:
        team = [p for p in players if p['TGID'] == tg]
        have = {r['PPOS'] for r in rows if r['TGID'] == tg}
        for slot in range(26):
            if slot in have:
                continue
            if slot <= 20:
                pool = sorted([p for p in team if p['PPOS'] == slot], key=lambda p: -p['POVR'])
            elif slot in (21, 22):
                pool = sorted([p for p in team if POS[p['PPOS']] in ('HB', 'WR', 'CB', 'FS', 'SS')], key=lambda p: -p['PKRT'])
            elif slot == 23:
                pool = sorted([p for p in team if POS[p['PPOS']] in ('K', 'P')], key=lambda p: (POS[p['PPOS']] != 'K', -p['PKPR']))
            elif slot == 24:
                pool = sorted([p for p in team if POS[p['PPOS']] == 'C'], key=lambda p: -p['POVR'])
            else:
                pool = sorted([p for p in team if POS[p['PPOS']] == 'HB'], key=lambda p: -p['POVR'])
            for dep, p in enumerate(pool[:2]):
                rows.append({'PGID': p['PGID'], 'TGID': tg, 'PPOS': slot, 'ddep': dep}); added.append((tg, slot))
    if added:
        rows.sort(key=lambda r: (r['PGID'], r['PPOS']))
        assert len(rows) <= D.cap
        blank = bytearray(D.reclen)
        for i, r in enumerate(rows):
            rec = bytearray(blank)
            for n in ('PGID', 'TGID', 'PPOS', 'ddep'):
                ty, bo, _, bc = DF[n]; rec = setbits(rec, bo, bc, r[n])
            d[D.dataoff + i * D.reclen:D.dataoff + (i + 1) * D.reclen] = rec
        struct.pack_into('<H', d, D.off + 22, len(rows))
        fix_crcs(d); open(path, 'wb').write(d)
    return len({a for a in added})


def delete_players(d, idxs):
    """Remove PLAY records (by index) and their depth-chart rows, keeping both tables packed."""
    bd = bytes(d); T, _ = parse(bd); P, D = T['PLAY'], T['DCHT']
    gone = set()
    for i in idxs:
        r = read(bd, P, i); gone.add((r['PGID'], r['TGID']))
    keep = [bd[P.dataoff + i * P.reclen:P.dataoff + (i + 1) * P.reclen] for i in range(P.cnt) if i not in idxs]
    d[P.dataoff:P.dataoff + P.cnt * P.reclen] = b''.join(keep) + bytes(P.reclen * (P.cnt - len(keep)))
    struct.pack_into('<H', d, P.off + 22, len(keep))
    left = []
    for i in range(D.cnt):
        r = read(bd, D, i)
        if (r['PGID'], r['TGID']) not in gone:
            left.append(bd[D.dataoff + i * D.reclen:D.dataoff + (i + 1) * D.reclen])
    d[D.dataoff:D.dataoff + D.cnt * D.reclen] = b''.join(left) + bytes(D.reclen * (D.cnt - len(left)))
    struct.pack_into('<H', d, D.off + 22, len(left))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('xlsx'); ap.add_argument('name', help='roster name, 8 letters or fewer, e.g. SQUADS1')
    ap.add_argument('--base', default=os.path.join(KIT, 'rosters', 'base', 'FF-299team-reserves.ros'))
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--no-copy', action='store_true', help="don't copy the roster into Documents\\Madden NFL 08\\Rosters")
    ap.add_argument('--allow-dupes', action='store_true')
    ap.add_argument('--keep-copies', action='store_true', help='send leftover reserve copies to free agency instead of deleting them')
    a = ap.parse_args()
    a.name = re.sub(r'[^A-Za-z0-9]', '', a.name)[:8] or 'ROSTER'

    os.makedirs(os.path.join(KIT, 'output'), exist_ok=True)
    report = []
    say = lambda s='': (print(s), report.append(s))
    settings, need, squads, players, notes = read_workbook(a.xlsx)
    base = bytearray(open(a.base, 'rb').read()); T, _ = parse(bytes(base))
    base_original = bytes(base)
    TM, P = T['TEAM'], T['PLAY']
    teams = {}
    for i in range(TM.cnt):
        r = read(bytes(base), TM, i); teams[(r['TLNA'] + ' ' + r['TDNA']).strip()] = r
        if r['TGID'] in RESERVE_TGIDS:
            teams.setdefault(r['TLNA'].strip(), r)          # reserves can be picked by city alone: "Broncos A"
    greats = {e['label']: e for e in json.load(open(os.path.join(KIT, 'data', 'greats_v3.json')))}

    errors, warns, skipped, op_hits, left_out = [], [], [], [], []
    allow = settings['allow']
    warns.extend(notes)
    errors.extend(CUSTOM_ERRORS)
    live = [s for s in squads if s['name']]
    if not live:
        sys.exit('No squads are named on Build Your Squads (Squad name row).')
    # Empty squads (placeholders, or squads whose players have no ready clone yet) are skipped, not errors.
    on_squad, ready_on = collections.Counter(), collections.Counter()
    for p in players:
        cu = p.get('custom')
        ok = (p['check'].upper().startswith('OK') and (bool(p['clone']) or bool(cu and cu['type'] == 'C'))
              and not (cu and not allow[cu['type']]))
        for k in set(p['ticks']):
            on_squad[k] += 1
            ready_on[k] += ok
    skipped_squads, skipped_slots = [], set()
    for s in live:
        if ready_on[s['slot']] == 0:
            skipped_slots.add(s['slot'])
            skipped_squads.append('%s: %s' % (s['name'], 'no players yet' if on_squad[s['slot']] == 0
                                              else '%d player(s), none with a ready clone yet' % on_squad[s['slot']]))
    live = [s for s in live if s['slot'] not in skipped_slots]
    if not live:
        sys.exit('None of the squads has a player with a ready clone yet, so there is nothing to build.')
    # count by the game's team id, so "Broncos A" and its full name can't sneak past as two teams
    used_teams = collections.Counter(teams[s['replaces']]['TGID'] for s in live if s['replaces'] in teams)
    dup_said = set()
    for s in live:
        if not s['replaces']:
            errors.append('Squad "%s": pick the team it replaces (Build Your Squads, Replaces row).' % s['name'])
        elif s['replaces'] not in teams:
            errors.append('Squad "%s": "%s" is not a team in this base roster.' % (s['name'], s['replaces']))
        elif used_teams[teams[s['replaces']]['TGID']] > 1 and teams[s['replaces']]['TGID'] not in dup_said:
            dup_said.add(teams[s['replaces']]['TGID'])
            others = [o['name'] for o in live if o is not s and o['replaces'] in teams
                      and teams[o['replaces']]['TGID'] == teams[s['replaces']]['TGID']]
            errors.append('Squad "%s" and squad "%s" both replace %s. Each squad needs its own team.' % (
                s['name'], '", "'.join(others), s['replaces']))
        if len(s['city']) > 17 or len(s['nick']) > 16:
            errors.append('Squad "%s": city is 17 letters max, nickname 16.' % s['name'])
    named = {s['slot'] for s in live}

    roster = {s['slot']: [] for s in live}
    for p in players:
        who = '%s %s (%s, row %d)' % (p['first'], p['last'], p['pos'] or '?', p['line'])
        for k in p['ticks']:
            if k in skipped_slots:
                continue
            if k not in named:
                warns.append('%s is ticked for squad slot %d, which has no name; ignored.' % (who, k)); continue
            cu = p.get('custom')
            if cu and not allow[cu['type']]:
                t = cu['type']
                left_out.append('%s on %s: NOT BUILT. He is %s and Allow %s is off on Build Your Squads. '
                                'Replace him on that squad, or tick Allow %s.' % (
                    who, squads[k - 1]['name'], 'B (edited clone)' if t == 'B' else 'C (from scratch)', t, t)); continue
            scratch = bool(cu and cu['type'] == 'C')
            if not p['check'].upper().startswith('OK') or not (p['clone'] or scratch):
                skipped.append('%s on %s: no valid clone yet' % (who, squads[k - 1]['name'])); continue
            if scratch and p['pos'] not in CP['template']:
                errors.append('%s: a from-scratch player needs a Position (F)' % who); continue
            e = greats.get(CP['template'][p['pos']] if scratch else p['clone'])
            if cu:
                e = custom_entry(e, cu, p['pos'], settings['cap'])
            if not e:
                errors.append('%s: clone "%s" is not in the ratings database' % (who, p['clone'])); continue
            if e['pos'] != p['pos']:
                errors.append('%s: position %s but the clone plays %s' % (who, p['pos'], e['pos'])); continue
            if re.fullmatch(r'\d+\.0+', p['jersey']):
                p['jersey'] = p['jersey'].split('.')[0]
            if p['jersey'] and not p['jersey'].isdigit():
                warns.append('%s: jersey "%s" is not a number; using the clone\'s' % (who, p['jersey'])); p['jersey'] = ''
            roster[k].append((p, e))
            hits = op_list(e, settings['op'])
            if hits:
                op_hits.append('%s (%s): %s' % (who, p['clone'], ', '.join(hits)))

    plan = {}
    for s in live:
        mine = roster[s['slot']]
        if not mine:
            errors.append('Squad "%s" has no players with an OK clone on it.' % s['name']); continue
        have = collections.Counter(p['pos'] for p, e in mine)
        gaps = {pos: n - have[pos] for pos, n in need.items() if n > have[pos]}
        total = len(mine) + sum(gaps.values())
        if total > settings['per_squad']:
            errors.append('Squad "%s": %d players + %d open spots = %d, over the %d limit.' % (
                s['name'], len(mine), sum(gaps.values()), total, settings['per_squad']))
        seen = collections.defaultdict(list)
        for p, e in mine:
            seen[(p['first'].lower(), p['last'].lower(), p['pos'])].append(p)
        for (f, l, pos), same in seen.items():
            if len(same) > 1:
                errors.append('SAME NAME, SAME POSITION on "%s": %s %s %s, rows %s' % (s['name'], same[0]['first'], same[0]['last'], pos, ', '.join(str(x['line']) for x in same)))
        jer = collections.defaultdict(list)
        for p, e in mine:
            if p['jersey']:
                jer[p['jersey']].append('%s %s' % (p['first'], p['last']))
        for j, names in jer.items():
            if len(names) > 1:
                warns.append('"%s": #%s is used by %s' % (s['name'], j, ', '.join(names)))
        plan[s['slot']] = dict(squad=s, mine=mine, gaps=gaps)

    title = 'MADDEN ROSTER BUILD: %s%s' % (a.name, '  [OP]' if op_hits else '')
    say(title)
    say('Workbook: %s   Base: %s' % (os.path.basename(a.xlsx), os.path.basename(a.base)))
    say()
    for s in live:
        pl = plan.get(s['slot'])
        if pl:
            say('  %-22s replaces %-22s %2d players, %2d open spots filled from %s' % (
                s['name'], s['replaces'] or '(no team picked)', len(pl['mine']), sum(pl['gaps'].values()), s['replaces'] or '?'))
    blocking = [e for e in errors if a.allow_dupes is False or not e.startswith('SAME NAME')]
    for head, items in (('SQUADS SKIPPED (nothing to build yet)', skipped_squads),
                        ('SKIPPED (pick a clone to include them)', skipped),
                        ('LEFT OUT: NOT ALLOWED (Build Your Squads toggles)', left_out), ('WARNINGS', warns),
                        ('OP PLAYERS (a rating over %d)' % settings['op'], op_hits), ('ERRORS (fix before building)', errors)):
        if items:
            say(); say('%s: %d' % (head, len(items)))
            for x in items:
                say('  - ' + x)
    rep_path = os.path.join(KIT, 'output', a.name + '_report.txt')
    if a.check_only or blocking:
        say(); say('Stopped before building.' if blocking else 'Check only: nothing built.')
        open(rep_path, 'w').write('\n'.join(report) + '\n'); sys.exit(1 if blocking else 0)

    # 1. Empty each replaced team except the best player at each open spot.
    PF = {f[2]: f for f in P.fields}
    allp = [read(bytes(base), P, i) for i in range(P.cnt)]
    kept, released, removed, short, drop = {}, {}, {}, [], set()
    for slot, pl in plan.items():
        tg = teams[pl['squad']['replaces']]['TGID']
        squad_team = sorted([(p['POVR'], i, p) for i, p in enumerate(allp) if p['TGID'] == tg], reverse=True)
        keep = set()
        for pos, n in pl['gaps'].items():
            at = [x for x in squad_team if POS[x[2]['PPOS']] == pos and x[1] not in keep][:n]
            if len(at) < n:
                short.append('%s: %s has only %d %s to fill %d open spot(s); that spot stays empty.' % (pl['squad']['name'], pl['squad']['replaces'], len(at), pos, n))
            keep.update(x[1] for x in at)
        kept[slot] = ['%s %s %s %d' % (POS[allp[i]['PPOS']], allp[i]['PFNA'], allp[i]['PLNA'], allp[i]['POVR']) for i in sorted(keep, key=lambda i: allp[i]['PPOS'])]
        released[slot] = 0; removed[slot] = 0
        for ovr, i, p in squad_team:
            if i in keep:
                continue
            if tg in RESERVE_TGIDS and not a.keep_copies:
                drop.add(i); removed[slot] += 1
                continue
            rec = B.rec_of(bytes(base), P, i); ty, bo, _, bc = PF['TGID']
            base[P.dataoff + i * P.reclen:P.dataoff + (i + 1) * P.reclen] = setbits(rec, bo, bc, FA)
            released[slot] += 1
    if drop:
        delete_players(base, drop)
    fix_crcs(base)
    tmp_base = os.path.join(KIT, 'output', a.name + '.base.tmp')
    open(tmp_base, 'wb').write(base)

    # 2. Add our players (one copy per ticked squad), rename teams, rebuild depth charts.
    rows, renames, skin_for = [], {}, {}
    for slot, pl in plan.items():
        s = pl['squad']; t = teams[s['replaces']]
        full = (t['TLNA'] + ' ' + t['TDNA']).strip()      # build_showdown looks teams up by full name
        for p, e in pl['mine']:
            rows.append([p['first'], p['last'], p['jersey'], p['pos'], e['label'], full])
        renames[full] = ((s['city'] or t['TLNA'])[:17], (s['nick'] or s['name'])[:16], 'XXX')
    B.SRC['__v6base__'] = tmp_base
    out_ros = os.path.join(KIT, 'output', a.name + '.ros'); tmp = out_ros + '.tmp'
    created, rel2, problems = B.build(rows, tmp, renames=renames, base='__v6base__', log=lambda *x: None, depth=True)
    changed = sanitize(tmp, a.base, out_ros)
    os.remove(tmp); os.remove(tmp_base)

    # 3. Skin tone for created players, in the order they were created.
    order = [p for slot, pl in plan.items() for p, e in pl['mine']]
    d = bytearray(open(out_ros, 'rb').read()); T2, _ = parse(bytes(d)); P2 = T2['PLAY']; PF2 = {f[2]: f for f in P2.fields}
    idx = {read(bytes(d), P2, i)['PGID']: i for i in range(P2.cnt)}
    # In Madden 08 the face (PFEx) carries the skin colour: in EA's roster every face belongs to one
    # skin tone. So when the sheet's skin tone differs from the clone's face, use a stock face of
    # that tone (picked from the player's name, so he gets the same face every build).
    face_skin, face_pool = face_tables(bytes(base_original))
    skins = faces = 0
    for (pgid, tg, pos, ovr, name, kr), p in zip(created, order):
        v = SKIN.get(p['skin'])
        if v is None:
            continue
        i = idx[pgid]; rec = B.rec_of(bytes(d), P2, i); ty, bo, _, bc = PF2['PSKI']
        rec = setbits(rec, bo, bc, v); skins += 1
        face = read(bytes(d), P2, i)['PFEx']
        if face_skin.get(face) != v and face_pool.get(v):
            pool = face_pool[v]
            new_face = pool[zlib.crc32(('%s %s' % (p['first'], p['last'])).lower().encode('utf-8')) % len(pool)]
            ty, bo, _, bc = PF2['PFEx']; rec = setbits(rec, bo, bc, new_face); faces += 1
        d[P2.dataoff + i * P2.reclen:P2.dataoff + (i + 1) * P2.reclen] = rec
    customs = apply_custom(d, P2, PF2, idx, created, [(p, e) for slot, pl in plan.items() for p, e in pl['mine']])
    fix_crcs(d); open(out_ros, 'wb').write(d)
    filled = fill_depth(out_ros, [teams[pl['squad']['replaces']]['TGID'] for pl in plan.values()])
    ok = verify(out_ros)

    say(); say('BUILT: %s  (%d players, checksums %s, %d bytes)' % (os.path.basename(out_ros), len(created),
                                                                 'valid' if ok else 'BAD', os.path.getsize(out_ros)))
    say('  skin tone set on %d players (%d given a face of that skin tone); %d empty depth-chart spots filled' % (skins, faces, filled))
    if customs:
        say('  custom players: %d' % len(customs))
        for x in customs:
            say('    - ' + x)
    for p in problems:
        say('  problem: ' + p)
    for x in short:
        say('  note: ' + x)
    for slot, pl in plan.items():
        s = pl['squad']; t = teams[s['replaces']]; c, n, _ = renames[(t['TLNA'] + ' ' + t['TDNA']).strip()]
        say(); say('%s  (in the game: %s %s, replacing %s)' % (s['name'], c, n, s['replaces']))
        gone = ('deleted (reserve copies): %d' % removed[slot]) if removed[slot] else ('sent to free agency: %d' % released[slot])
        say('  your players: %d   kept from %s for open spots: %d   %s' % (
            len(pl['mine']), s['replaces'], len(kept[slot]), gone))
        if kept[slot]:
            say('  kept: ' + '; '.join(kept[slot]))
        filled_gaps = sum(pl['gaps'].values())
        if filled_gaps:
            say('  note: %d required spot(s) were empty, so the best %s players at those positions stay on the team.' % (filled_gaps, s['replaces']))
        elif len(pl['mine']) < settings['per_squad']:
            say('  note: your players only, %d of %d. The other roster spots stay empty.' % (len(pl['mine']), settings['per_squad']))
    open(rep_path, 'w').write('\n'.join(report) + '\n')
    dest = None if a.no_copy else madden_rosters_folder()
    if dest:
        target = os.path.join(dest, a.name + '.ros')
        replaced = os.path.exists(target)
        shutil.copy2(out_ros, target)
        say(); say('COPIED to %s%s' % (target, '  (replaced the older file with this name)' if replaced else ''))
        say('Next: in Madden, Main Menu > Menu > Files > Load, and pick %s.' % a.name)
    else:
        say(); say('Next: copy %s.ros into Documents\\Madden NFL 08\\Rosters, then Main Menu > Menu > Files > Load.' % a.name)
        if not a.no_copy:
            say('(Could not find Documents\\Madden NFL 08\\Rosters on this PC, so it was not copied there.)')
    open(rep_path, 'w').write('\n'.join(report) + '\n')


if __name__ == '__main__':
    main()
