import sys,struct,csv,json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from tdb import parse,read
from crcs import ALGS
crc=ALGS['mpeg2']
FA_FIELDS={'TGID':1009,'PCON':0,'PCYL':0,'PSBO':0,'PVSB':0,'PTSA':0,'PSXP':1880,'PCMT':1023,
           'PLPL':0,'PMOR':99,'PROL':45,'PDPI':63,'PDRO':15,'PYWT':0,'PJTY':0,'PPTI':1023,'PFPB':0,'PMPC':0}
def setbits(rec,bo,bc,val):
    n=int.from_bytes(rec,'little'); m=((1<<bc)-1)<<bo
    n=(n&~m)|((val<<bo)&m); return bytearray(n.to_bytes(len(rec),'little'))
def setstr(rec,bo,bc,s):
    b=s.encode('latin1')[:bc//8-1]; b=b+b'\0'*(bc//8-len(b)); rec[bo//8:bo//8+bc//8]=b; return rec
def build(src,dst,clones):
    """clones: list of dict(first,last,jersey,src_index)"""
    d=bytearray(open(src,'rb').read())
    T,tabs=parse(bytes(d)); p=T['PLAY']; F={f[2]:f for f in p.fields}
    rows=[read(bytes(d),p,i) for i in range(p.cnt)]
    used={r['PGID'] for r in rows}|{r['POID'] for r in rows}
    free=(x for x in range(30000,32700) if x not in used)
    assert p.cnt+len(clones)<=p.cap
    made=[]
    for k,c in enumerate(clones):
        i=c['src_index']; rec=bytearray(d[p.dataoff+i*p.reclen:p.dataoff+(i+1)*p.reclen])
        nid=next(free)
        vals=dict(FA_FIELDS); vals['PGID']=nid; vals['POID']=nid; vals['PJEN']=int(c['jersey'])
        if c.get('team') is not None: vals['TGID']=int(c['team'])
        for n,v in vals.items():
            ty,bo,_,bc=F[n]; rec=setbits(rec,bo,bc,v)
        rec=setstr(rec,F['PFNA'][1],F['PFNA'][3],c['first'])
        rec=setstr(rec,F['PLNA'][1],F['PLNA'][3],c['last'])
        j=p.cnt+k; d[p.dataoff+j*p.reclen:p.dataoff+(j+1)*p.reclen]=rec
        made.append((c['first'],c['last'],nid))
    struct.pack_into('<H',d,p.off+22,p.cnt+len(clones))
    fix_crcs(d)
    open(dst,'wb').write(d); return made
def fix_crcs(d):
    T,tabs=parse(bytes(d)); names=[n for n,_ in tabs]
    struct.pack_into('<I',d,0x14,crc(bytes(d[0:0x14])))
    first=T[names[0]]; lst_end=first.off
    struct.pack_into('<I',d,first.off,crc(bytes(d[0x18:lst_end])))
    offs=[T[n].off for n in names]+[len(d)-4]
    for i,n in enumerate(names):
        t=T[n]
        struct.pack_into('<I',d,t.off+36,crc(bytes(d[t.off+4:t.off+36])))
        v=crc(bytes(d[t.off+40:offs[i+1]]))
        if i+1<len(names): struct.pack_into('<I',d,T[names[i+1]].off,v)
        else: struct.pack_into('<I',d,len(d)-4,v)
def verify(path):
    d=open(path,'rb').read(); dd=bytearray(d); fix_crcs(dd); return bytes(dd)==d
