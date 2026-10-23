import struct,sys
class Table:
    pass
def parse(data):
    assert data[:2]==b'DB'
    ntab=struct.unpack_from('<I',data,0x10)[0]
    lst=0x18; base=lst+8*ntab
    tabs=[]
    for i in range(ntab):
        name=data[lst+8*i:lst+8*i+4].decode()
        off=struct.unpack_from('<I',data,lst+8*i+4)[0]
        tabs.append((name,base+off))
    out={}
    for idx,(name,o) in enumerate(tabs):
        t=Table(); t.name=name; t.off=o
        (t.crc,t.u1,t.reclen,t.recbits,t.u2,t.cap,t.cnt,t.u3,t.nf,t.ni,t.u4,t.u5,t.hcrc)=struct.unpack_from('<IIIIIHHIBBHII',data,o)
        fo=o+40
        t.fields=[]
        for j in range(t.nf):
            ty,bo,nm,bc=struct.unpack_from('<II4sI',data,fo+16*j)
            t.fields.append((ty,bo,nm.decode('latin1'),bc))
        t.dataoff=fo+16*t.nf
        out[name]=t
    return out,tabs
def getbits(rec,bo,bc):
    return (int.from_bytes(rec,'little')>>bo)&((1<<bc)-1)
def read(data,t,i):
    rec=data[t.dataoff+i*t.reclen:t.dataoff+(i+1)*t.reclen]
    r={}
    for ty,bo,nm,bc in t.fields:
        if ty==0:
            s=rec[bo//8:bo//8+bc//8]; r[nm]=s.split(b'\0')[0].decode('latin1')
        else:
            r[nm]=getbits(rec,bo,bc)
    return r
