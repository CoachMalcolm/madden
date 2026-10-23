"""Madison Madden 08 roster builder.

Turns the player spreadsheet (exported as CSV) into a Madden 08 .ros roster file.

    python madden_build.py input/players.csv MAGOLD5
    python madden_build.py input/players.csv MAGOLD5 --teams input/teams.csv --base rosters/base/FF-223team-base.ros

The CSV is the "Alumni & Teammates" tab: File > Download > Comma-separated values.
Only rows with a Madden Team AND a Clone check starting with "OK" are built.
"""
import argparse, csv, collections, os, re, sys

KIT = os.environ.get('MADDEN_KIT') or os.path.dirname(os.path.abspath(__file__))   # MADDEN_KIT: set by the Windows program
sys.path.insert(0, os.path.join(KIT, 'lib'))
import build_showdown as B
from sanitize import sanitize
from clone import verify
from tdb import parse, read

POS = B.POS


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def load_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        rows = list(csv.reader(fh))
    head_i = next((i for i, r in enumerate(rows) if any(clean(c).lower().startswith('first') for c in r)), None)
    if head_i is None:
        sys.exit('Could not find the header row (a column starting with "First").')
    head = [clean(c).lower() for c in rows[head_i]]

    def col(test):
        return next((i for i, h in enumerate(head) if test(h)), None)
    c = dict(first=col(lambda h: h.startswith('first')), last=col(lambda h: h.startswith('last')),
             jersey=col(lambda h: h in ('#', 'jersey', 'jersey #')), pos=col(lambda h: h.startswith('position')),
             clone=col(lambda h: 'clone' in h and 'check' not in h), check=col(lambda h: h.startswith('clone check')),
             team=col(lambda h: h.startswith('madden team')))
    missing = [k for k, v in c.items() if v is None]
    if missing:
        sys.exit('CSV is missing columns: %s' % ', '.join(missing))
    out = []
    for n, r in enumerate(rows[head_i + 1:], start=head_i + 2):
        g = lambda k: clean(r[c[k]]) if c[k] < len(r) else ''
        if g('first') or g('last'):
            out.append(dict(line=n, first=g('first'), last=g('last'), jersey=g('jersey'), pos=g('pos'),
                            clone=g('clone'), check=g('check'), team=g('team')))
    return out


def load_teams(path):
    if not path:
        return {}
    with open(path, newline='', encoding='utf-8-sig') as fh:
        return {clean(r['Madden Team']): (clean(r['New City']), clean(r['New Nickname']))
                for r in csv.DictReader(fh) if clean(r.get('Madden Team'))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv'); ap.add_argument('name', help='output name, e.g. MAGOLD5 (8 letters or fewer is safest)')
    ap.add_argument('--base', default=os.path.join(KIT, 'rosters', 'base', 'FF-223team-base.ros'),
                    help='base roster that matches the mod installed on the PC')
    ap.add_argument('--teams', help='CSV with columns: Madden Team, New City, New Nickname')
    ap.add_argument('--no-depth', action='store_true', help="keep the base roster's depth chart")
    ap.add_argument('--check-only', action='store_true', help='run the checks and stop')
    ap.add_argument('--allow-dupes', action='store_true', help='build even if a name repeats at the same position')
    a = ap.parse_args()
    if a.csv.lower().endswith('.xlsx'):
        sys.exit('That is a v6 workbook (.xlsx). Use BUILD_V6.bat (or: python madden_build_v6.py "%s" %s).' % (a.csv, a.name))

    os.makedirs(os.path.join(KIT, 'output'), exist_ok=True)
    out_ros = os.path.join(KIT, 'output', a.name + '.ros')
    report = []
    say = lambda s='': (print(s), report.append(s))

    B.SRC['__base__'] = a.base
    base = open(a.base, 'rb').read(); T, _ = parse(base)
    team_names = {(r['TLNA'] + ' ' + r['TDNA']).strip() for r in (read(base, T['TEAM'], i) for i in range(T['TEAM'].cnt))}
    import json
    greats = {e['label']: e for e in json.load(open(os.path.join(KIT, 'data', 'greats_v3.json')))}

    rows = load_rows(a.csv); renames = load_teams(a.teams)
    say('MADDEN ROSTER BUILD: %s' % a.name)
    say('Sheet: %s   Base: %s (%d teams)' % (os.path.basename(a.csv), os.path.basename(a.base), len(team_names)))
    say()

    build, skipped, errors, warns = [], [], [], []
    for r in rows:
        who = '%s %s (%s, line %d)' % (r['first'], r['last'], r['pos'] or '?', r['line'])
        if not r['team']:
            continue
        if not r['check'].upper().startswith('OK') or not r['clone']:
            skipped.append('%s -> %s: no valid clone yet' % (who, r['team'])); continue
        e = greats.get(r['clone'])
        if not e:
            errors.append('%s: clone "%s" not found in the ratings database' % (who, r['clone'])); continue
        if e['pos'] != r['pos']:
            errors.append('%s: position %s but clone plays %s' % (who, r['pos'], e['pos'])); continue
        if r['team'] not in team_names:
            errors.append('%s: team "%s" is not in this base roster' % (who, r['team'])); continue
        if re.fullmatch(r'\d+\.0+', r['jersey']):
            r['jersey'] = r['jersey'].split('.')[0]
        if r['jersey'] and not r['jersey'].isdigit():
            warns.append('%s: jersey "%s" is not a number; using the clone\'s' % (who, r['jersey'])); r['jersey'] = ''
        build.append(r)

    seen = collections.defaultdict(list)
    for r in build:
        seen[(r['first'].lower(), r['last'].lower(), r['pos'])].append(r)
    dupes = [v for v in seen.values() if len(v) > 1]
    for v in dupes:
        errors.append('SAME NAME, SAME POSITION: %s %s %s on lines %s' % (v[0]['first'], v[0]['last'], v[0]['pos'],
                                                                        ', '.join(str(x['line']) for x in v)))
    jer = collections.defaultdict(list)
    for r in build:
        if r['jersey']:
            jer[(r['team'], r['jersey'])].append('%s %s' % (r['first'], r['last']))
    for (t, j), names in jer.items():
        if len(names) > 1:
            warns.append('%s: #%s is used by %s' % (t, j, ', '.join(names)))
    for t in renames:
        if t not in team_names:
            errors.append('teams file: "%s" is not in this base roster' % t)

    per = collections.Counter(r['team'] for r in build)
    say('Players to build: %d' % len(build))
    for t, n in per.most_common():
        nc = renames.get(t)
        say('  %-24s %3d players%s' % (t, n, ('  -> renamed "%s %s"' % nc) if nc else ''))
    for title, items in (('SKIPPED (pick a clone to include them)', skipped), ('WARNINGS', warns), ('ERRORS (fix before building)', errors)):
        if items:
            say(); say('%s: %d' % (title, len(items)))
            for s in items: say('  - ' + s)
    blocking = [e for e in errors if a.allow_dupes is False or not e.startswith('SAME NAME')]
    if a.check_only or blocking:
        say(); say('Stopped before building.' if blocking else 'Check only: nothing built.')
        open(os.path.join(KIT, 'output', a.name + '_report.txt'), 'w').write('\n'.join(report) + '\n')
        sys.exit(1 if blocking else 0)

    tmp = out_ros + '.tmp'
    sheet_rows = [[r['first'], r['last'], r['jersey'], r['pos'], r['clone'], r['team']] for r in build]
    ren = {t: (c[:17], n[:16], None) for t, (c, n) in renames.items()}
    created, released, problems = B.build(sheet_rows, tmp, renames={t: (c, n, 'XXX') for t, (c, n, _) in ren.items()},
                                          base='__base__', log=lambda *x: None, depth=not a.no_depth)
    changed = sanitize(tmp, a.base, out_ros)     # also puts back the original team abbreviations
    os.remove(tmp)
    ok = verify(out_ros)
    say(); say('BUILT: %s  (%d players, checksums %s, %d bytes)' % (os.path.basename(out_ros), len(created),
                                                                 'valid' if ok else 'BAD', os.path.getsize(out_ros)))
    for tg, lst in released.items():
        say('  team %d: released %d lowest-rated NFL players to free agency' % (tg, len(lst)))
    look = {k: v for k, v in changed.items() if k != 'team abbr restored'}
    if look:
        say('  look settings matched to the base roster: ' + ', '.join('%s x%d' % kv for kv in sorted(look.items())))
    for p in problems:
        say('  problem: ' + p)

    d = open(out_ros, 'rb').read(); T, _ = parse(d)
    P = {read(d, T['PLAY'], i)['PGID']: read(d, T['PLAY'], i) for i in range(T['PLAY'].cnt)}
    tg_of = {c[1] for c in created}
    names = {read(d, T['TEAM'], i)['TGID']: (read(d, T['TEAM'], i)['TLNA'] + ' ' + read(d, T['TEAM'], i)['TDNA']) for i in range(T['TEAM'].cnt)}
    starters = collections.defaultdict(dict)
    for i in range(T['DCHT'].cnt):
        r = read(d, T['DCHT'], i)
        if r['TGID'] in tg_of and r['ddep'] == 0 and r['PPOS'] < 21:
            starters[r['TGID']][POS[r['PPOS']]] = P[r['PGID']]
    for tg in sorted(tg_of):
        say(); say('Starters, %s:' % names[tg])
        say('  ' + '  '.join('%s %s %s' % (pos, starters[tg][pos]['PFNA'][:1] + '.', starters[tg][pos]['PLNA']) for pos in POS if pos in starters[tg]))
    open(os.path.join(KIT, 'output', a.name + '_report.txt'), 'w').write('\n'.join(report) + '\n')
    say(); say('Next: copy %s.ros into Documents\\Madden NFL 08\\Rosters, then Main Menu > Menu > Files > Load.' % a.name)


if __name__ == '__main__':
    main()
