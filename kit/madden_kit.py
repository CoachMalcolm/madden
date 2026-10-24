"""Madden Roster Kit: one front door for every way of building a roster.

Double-click (or run with no arguments) and it asks for your list. You can give it:
  - a Google Sheets link to your Master Madden List (shared "Anyone with the link"),
  - the workbook downloaded as .xlsx (File > Download > Microsoft Excel),
  - the workbook's CSV files (File > Download > Comma-separated values) for the Players and
    Build Your Squads tabs, and Settings if you like; drop the files or the folder that holds them,
  - an old v5 player list saved as .csv (the "Alumni & Teammates" tab).

Every roster and report goes into output\\YYYYMM (the month it was built), and anything already
loose in output is sorted into month folders too. The roster is also copied into
Documents\\Madden NFL 08\\Rosters, as before.

    python madden_kit.py                      (asks for everything)
    python madden_kit.py "C:\\path\\My List.xlsx" SQUADS1
    python madden_kit.py https://docs.google.com/spreadsheets/d/.../edit SQUADS1
"""
import csv, datetime, glob, io, os, re, shutil, sys, urllib.request, zipfile
from xml.sax.saxutils import escape

FROZEN = getattr(sys, 'frozen', False)
for _s in (sys.stdout, sys.stderr):                  # Windows consoles can't print every character
    try:
        _s.reconfigure(errors='replace')
    except Exception:
        pass
KIT = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
os.environ['MADDEN_KIT'] = KIT                       # the builders read data and write output here
sys.path.insert(0, os.path.join(KIT, 'lib'))

import madden_build_v6 as V6                          # noqa: E402  (after MADDEN_KIT is set)
import madden_build as V5                             # noqa: E402
# The lib modules are imported by the builders through sys.path; naming them here lets the
# Windows program include them.
import build_showdown, clone, crcs, sanitize, tdb, xlsx  # noqa: E402,F401

OUT = os.path.join(KIT, 'output')
INPUT = os.path.join(KIT, 'input')
TABS = ('Settings', 'Build Your Squads', 'Players')

# Settings used when the CSVs don't include the Settings tab (the workbook's own defaults).
DEFAULT_NEED = [('QB', 1), ('HB', 1), ('FB', 1), ('WR', 3), ('TE', 1), ('LT', 1), ('LG', 1), ('C', 1), ('RG', 1),
                ('RT', 1), ('LE', 1), ('RE', 1), ('DT', 2), ('LOLB', 1), ('MLB', 1), ('ROLB', 1), ('CB', 3),
                ('FS', 1), ('SS', 1), ('K', 1), ('P', 1)]


def say(s=''):
    print(s, flush=True)


def ask(prompt):
    try:
        return input(prompt)
    except EOFError:
        return ''


def unquote(s):
    return s.strip().strip('"').strip("'").strip()


# ---------- month folders ----------

def month_dir(ts=None):
    d = datetime.datetime.fromtimestamp(ts) if ts else datetime.datetime.now()
    path = os.path.join(OUT, d.strftime('%Y%m'))
    os.makedirs(path, exist_ok=True)
    return path


def sort_output():
    """Move every loose file in output into the folder for the month it was made."""
    os.makedirs(OUT, exist_ok=True)
    moved = 0
    for f in os.listdir(OUT):
        p = os.path.join(OUT, f)
        if os.path.isfile(p) and not f.endswith('.tmp'):
            dest = os.path.join(month_dir(os.path.getmtime(p)), f)
            if os.path.exists(dest):
                os.remove(dest)
            shutil.move(p, dest)
            moved += 1
    return moved


# ---------- inputs ----------

def sheet_id(text):
    m = re.search(r'docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})', text)
    return m.group(1) if m else None


def download_sheet(sid):
    """Download a shared Google Sheet as .xlsx into input\\."""
    os.makedirs(INPUT, exist_ok=True)
    url = 'https://docs.google.com/spreadsheets/d/%s/export?format=xlsx' % sid
    say('Downloading the workbook from Google Sheets ...')
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
            disp = r.headers.get('Content-Disposition', '')
    except Exception as e:
        sys.exit('Could not download the workbook (%s).\nCheck the link, and that the sheet is shared as '
                 '"Anyone with the link". Or download it yourself: File > Download > Microsoft Excel (.xlsx).' % e)
    if not data.startswith(b'PK'):
        sys.exit('Google sent back a sign-in page instead of the workbook. Share the sheet as "Anyone with the link" '
                 '(Share > General access), or download it yourself: File > Download > Microsoft Excel (.xlsx).')
    m = re.search(r"filename\*=UTF-8''([^;]+)", disp) or re.search(r'filename="([^"]+)"', disp)
    name = urllib.request.unquote(m.group(1)) if m else 'Google Sheet %s.xlsx' % sid[:8]
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    path = os.path.join(INPUT, name)
    with open(path, 'wb') as fh:
        fh.write(data)
    say('Saved %s' % path)
    return path


def csv_tab(path):
    """Which workbook tab a CSV came from: Google names them "<workbook> - <tab>.csv"."""
    base = os.path.splitext(os.path.basename(path))[0].lower()
    for tab in TABS:
        t = tab.lower()
        if base == t or base.endswith(' - ' + t) or base.endswith('-' + t) or base.endswith('_' + t.replace(' ', '_')):
            return tab
    return None


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        return list(csv.reader(fh))


def is_v5_csv(path):
    rows = read_csv(path)[:15]
    heads = [c.strip().lower() for r in rows for c in r]
    return any(h.startswith('madden team') for h in heads)


def cell_xml(ref, v):
    if v is None or v == '':
        return ''
    s = str(v).strip()
    if s.upper() in ('TRUE', 'FALSE'):
        return '<c r="%s" t="b"><v>%d</v></c>' % (ref, s.upper() == 'TRUE')
    if re.fullmatch(r'-?\d+(\.\d+)?', s):
        return '<c r="%s"><v>%s</v></c>' % (ref, s)
    return '<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (ref, escape(s))


def col_letters(i):
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def default_settings_rows():
    rows = [[''] * 8 for _ in range(26)]
    rows[4][1], rows[5][1], rows[6][1] = '127', '99', '55'          # B5 cap, B6 OP, B7 per squad
    for k, (p, n) in enumerate(DEFAULT_NEED):
        rows[4 + k][6], rows[4 + k][7] = p, str(n)                    # G5:H25
    return rows


def csvs_to_xlsx(files):
    """Turn the Players / Build Your Squads (/ Settings) CSVs into a small .xlsx the builder reads."""
    tabs = {}
    for f in files:
        t = csv_tab(f)
        if t:
            tabs[t] = read_csv(f)
    missing = [t for t in ('Players', 'Build Your Squads') if t not in tabs]
    if missing:
        sys.exit('Missing the CSV for: %s.\nIn Google Sheets, open that tab, then File > Download > '
                 'Comma-separated values, and give me all the CSV files together.' % ', '.join(missing))
    if 'Settings' not in tabs:
        say('No Settings CSV: using the standard settings (55 a squad, 26 required spots).')
        tabs['Settings'] = default_settings_rows()
    os.makedirs(INPUT, exist_ok=True)
    out = os.path.join(INPUT, 'from CSV files.xlsx')
    sheets = ['Settings', 'Build Your Squads', 'Players']
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + ''.join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1)
                             for i in range(len(sheets))) + '</Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + ''.join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(n), i + 1, i + 1) for i, n in enumerate(sheets))
                   + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + ''.join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1)
                             for i in range(len(sheets))) + '</Relationships>')
        for i, n in enumerate(sheets):
            body = []
            for r, row in enumerate(tabs[n]):
                cells = ''.join(cell_xml('%s%d' % (col_letters(c), r + 1), v) for c, v in enumerate(row))
                if cells:
                    body.append('<row r="%d">%s</row>' % (r + 1, cells))
            z.writestr('xl/worksheets/sheet%d.xml' % (i + 1),
                       '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                       + ''.join(body) + '</sheetData></worksheet>')
    return out


def gather(args):
    """Turn whatever was given (link, files, folder) into ('v6', xlsx) or ('v5', csv)."""
    items = [unquote(a) for a in args if unquote(a)]
    if len(items) == 1 and sheet_id(items[0]):
        return 'v6', download_sheet(sheet_id(items[0]))
    files = []
    for it in items:
        if os.path.isdir(it):
            files += sorted(glob.glob(os.path.join(it, '*.xlsx')) + glob.glob(os.path.join(it, '*.csv')))
        elif os.path.isfile(it):
            files.append(it)
        else:
            sys.exit('Can\'t find "%s". Drag the file into this window, or paste a Google Sheets link.' % it)
    xl = [f for f in files if f.lower().endswith('.xlsx')]
    cs = [f for f in files if f.lower().endswith('.csv')]
    if xl:
        if len(xl) > 1:
            sys.exit('More than one .xlsx given. Give me one workbook at a time.')
        return 'v6', xl[0]
    if not cs:
        sys.exit('Give me a Google Sheets link, an .xlsx workbook, or CSV files.')
    if len(cs) == 1 and is_v5_csv(cs[0]):          # old v5 list: has a "Madden Team" column
        return 'v5', cs[0]
    if any(csv_tab(f) for f in cs):
        return 'v6', csvs_to_xlsx(cs)
    sys.exit('These CSV files don\'t look like the Master Madden List tabs (Players, Build Your Squads) '
             'or an old v5 list (with a "Madden Team" column).')


# ---------- run ----------

def run_builder(module, argv):
    old = sys.argv
    sys.argv = [module.__file__] + argv
    try:
        module.main()
        return 0
    except SystemExit as e:
        if isinstance(e.code, str):
            say(e.code)
            return 1
        return e.code or 0
    finally:
        sys.argv = old


def main(argv):
    say('MADDEN ROSTER KIT')
    say('=================')
    flags = [a for a in argv if a.startswith('--')]
    rest = [a for a in argv if not a.startswith('--')]
    name = None
    if len(rest) >= 2 and re.fullmatch(r'[A-Za-z0-9 ]{1,12}', rest[-1]) and not os.path.exists(unquote(rest[-1])):
        name = rest.pop()
    if not rest:
        say('Paste your Google Sheets link, or drag your workbook (.xlsx) or CSV files into this window,')
        src = ask('then press Enter: ')
        rest = re.findall(r'"[^"]+"|\S+', src)
    kind, src = gather(rest)
    if not name:
        name = ask('Roster name, letters and numbers only, 8 or fewer (e.g. SQUADS1): ')
    name = re.sub(r'[^A-Za-z0-9]', '', name or '')[:8] or 'ROSTER'

    moved = sort_output()
    if moved:
        say('Sorted %d older file%s in output into month folders.' % (moved, '' if moved == 1 else 's'))
    say()
    if kind == 'v6':
        code = run_builder(V6, [src, name] + flags)
    else:
        teams = os.path.join(INPUT, 'teams.csv')
        v5flags = [f for f in flags if f in ('--check-only', '--allow-dupes', '--no-depth')]   # it never copies, so no --no-copy
        code = run_builder(V5, [src, name] + (['--teams', teams] if os.path.exists(teams) else []) + v5flags)
    # File this build's roster and report in this month's folder.
    dest = month_dir()
    for f in glob.glob(os.path.join(OUT, name + '*')):
        if os.path.isfile(f) and not f.endswith('.tmp'):
            target = os.path.join(dest, os.path.basename(f))
            if os.path.exists(target):
                os.remove(target)
            shutil.move(f, target)
    say()
    if code == 0 and os.path.exists(os.path.join(dest, name + '.ros')):
        say('Done. Roster and report: %s' % dest)
    else:
        say('Nothing was built. Read the messages above, fix them, and run it again.')
    return code


if __name__ == '__main__':
    # Always show what happened and wait, so the window never just vanishes.
    try:
        code = main(sys.argv[1:])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if isinstance(e.code, str):
            say(); say(e.code)
    except BaseException:
        import traceback
        code = 1
        say(); say('Something went wrong. Please send this to Malcolm:'); say(traceback.format_exc())
    if code:
        say(); say('Nothing was built.')
    if FROZEN or os.environ.get('MADDEN_PAUSE'):
        ask('\nPress Enter to close.')
    sys.exit(code)
