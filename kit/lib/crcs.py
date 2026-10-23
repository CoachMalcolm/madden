def mk(poly,refin,init,xorout):
    tbl=[]
    if refin:
        rp=int('{:032b}'.format(poly)[::-1],2)
        for i in range(256):
            c=i
            for _ in range(8): c=(c>>1)^rp if c&1 else c>>1
            tbl.append(c)
        def f(b):
            c=init
            for x in b: c=(c>>8)^tbl[(c^x)&0xff]
            return c^xorout
    else:
        for i in range(256):
            c=i<<24
            for _ in range(8): c=((c<<1)^poly)&0xffffffff if c&0x80000000 else (c<<1)&0xffffffff
            tbl.append(c)
        def f(b):
            c=init
            for x in b: c=((c<<8)&0xffffffff)^tbl[((c>>24)^x)&0xff]
            return c^xorout
    return f
ALGS={'crc32':mk(0x04C11DB7,True,0xffffffff,0xffffffff),'bzip2':mk(0x04C11DB7,False,0xffffffff,0xffffffff),
'mpeg2':mk(0x04C11DB7,False,0xffffffff,0),'posix':mk(0x04C11DB7,False,0,0xffffffff),'jam':mk(0x04C11DB7,True,0xffffffff,0),'zero':mk(0x04C11DB7,False,0,0)}
