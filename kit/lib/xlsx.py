"""Read values from an .xlsx file (File > Download > Microsoft Excel from Google Sheets).
Standard library only, so nothing extra has to be installed on the PC."""
import re, zipfile
import xml.etree.ElementTree as ET

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


class Workbook:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        wb = ET.fromstring(self.z.read('xl/workbook.xml'))
        rels = ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels'))
        target = {r.get('Id'): r.get('Target') for r in rels.findall('p:Relationship', NS)}
        self.sheets = {}
        for s in wb.find('m:sheets', NS):
            t = target[s.get('{%s}id' % NS['r'])].lstrip('/')
            self.sheets[s.get('name')] = t if t.startswith('xl/') else 'xl/' + t
        self.strings = []
        if 'xl/sharedStrings.xml' in self.z.namelist():
            for si in ET.fromstring(self.z.read('xl/sharedStrings.xml')).findall('m:si', NS):
                self.strings.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))

    def sheet(self, name):
        """Return {(row, col): value} with 0-based row and column."""
        if name not in self.sheets:
            raise KeyError('The workbook has no "%s" tab.' % name)
        root = ET.fromstring(self.z.read(self.sheets[name]))
        cells = {}
        for c in root.iter('{%s}c' % NS['m']):
            m = re.match(r'([A-Z]+)(\d+)', c.get('r'))
            key = (int(m.group(2)) - 1, col_index(m.group(1)))
            t = c.get('t'); v = c.find('m:v', NS)
            if t == 'inlineStr':
                val = ''.join(x.text or '' for x in c.iter('{%s}t' % NS['m']))
            elif v is None:
                continue
            elif t == 's':
                val = self.strings[int(v.text)]
            elif t == 'b':
                val = v.text == '1'
            elif t in ('str', 'e'):
                val = v.text or ''
            else:
                f = float(v.text)
                val = int(f) if f.is_integer() else f
            cells[key] = val
        return cells


def cell(cells, a1):
    m = re.match(r'([A-Z]+)(\d+)', a1)
    return cells.get((int(m.group(2)) - 1, col_index(m.group(1))), '')
