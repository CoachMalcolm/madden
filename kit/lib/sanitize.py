"""Post-process a built roster: make created players' look fields safe for a stock game,
and optionally put back the original team abbreviation / short name."""
import sys, collections
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from tdb import parse, read
from clone import setbits, setstr, fix_crcs
RATINGS = set('PSPD PACC PAGI PSTR PAWR PCTH PCAR PBTK PJMP PTHP PTHA PPBK PRBK PTAK PKPR PKAC PKRT PSTA PINJ PTGH POVR PHGT PWGT PAGE PPOS POPS PJEN PGID POID TGID PFNA PLNA'.split())
def sanitize(src, stock, out, restore_abbr=True, look=True):
    d = bytearray(open(src, 'rb').read()); s = open(stock, 'rb').read()
    T, _ = parse(bytes(d)); S, _ = parse(s)
    P = T['PLAY']; PF = {f[2]: f for f in P.fields}
    sp = [read(s, S['PLAY'], i) for i in range(S['PLAY'].cnt)]
    seen = {k: collections.Counter(p[k] for p in sp) for k in sp[0] if k not in RATINGS and not isinstance(sp[0][k], str)}
    small = {k: c for k, c in seen.items() if len(c) <= 40}
    changed = collections.Counter()
    if look:
        for i in range(P.cnt):
            p = read(bytes(d), P, i)
            if p['PGID'] < 30000: continue
            rec = bytearray(d[P.dataoff+i*P.reclen:P.dataoff+(i+1)*P.reclen])
            for k, c in small.items():
                if p[k] not in c:
                    ty, bo, _, bc = PF[k]; rec = setbits(rec, bo, bc, c.most_common(1)[0][0]); changed[k] += 1
            d[P.dataoff+i*P.reclen:P.dataoff+(i+1)*P.reclen] = rec
    if restore_abbr:
        TM = T['TEAM']; TF = {f[2]: f for f in TM.fields}
        orig = {read(s, S['TEAM'], i)['TGID']: read(s, S['TEAM'], i) for i in range(S['TEAM'].cnt)}
        for i in range(TM.cnt):
            r = read(bytes(d), TM, i); o = orig.get(r['TGID'])
            if o and (r['TSNA'] != o['TSNA'] or r['TMNC'] != o['TMNC']):
                rec = bytearray(d[TM.dataoff+i*TM.reclen:TM.dataoff+(i+1)*TM.reclen])
                rec = setstr(rec, TF['TSNA'][1], TF['TSNA'][3], o['TSNA'])
                rec = setstr(rec, TF['TMNC'][1], TF['TMNC'][3], o['TMNC'])
                d[TM.dataoff+i*TM.reclen:TM.dataoff+(i+1)*TM.reclen] = rec; changed['team abbr restored'] += 1
    fix_crcs(d); open(out, 'wb').write(d)
    return changed
