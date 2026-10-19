# -*- coding: utf-8 -*-
r"""부록 대본 FUROKU/SCENARIO.DOC(Word 6/95) → work/scenario.txt
  OLE 복합 문서 → WordDocument 스트림의 본문(글자마다 u16, 0x100 이상 = SJIS 코드).
  python tools/scenario.py
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'disc', 'FUROKU', 'SCENARIO.DOC')
OUT = os.path.join(ROOT, 'work', 'scenario.txt')


def ole_streams(b):
    ss = 1 << struct.unpack_from('<H', b, 30)[0]
    mss = 1 << struct.unpack_from('<H', b, 32)[0]
    ndif = struct.unpack_from('<I', b, 44)[0]
    dir0 = struct.unpack_from('<I', b, 48)[0]
    cutoff = struct.unpack_from('<I', b, 56)[0]
    mfat0, nmfat = struct.unpack_from('<II', b, 60)
    difat = list(struct.unpack_from('<109I', b, 76))
    d = struct.unpack_from('<I', b, 68)[0]
    sec = lambda i: b[512 + i * ss:512 + (i + 1) * ss]
    for _ in range(struct.unpack_from('<I', b, 72)[0]):
        s = sec(d); difat += struct.unpack_from('<%dI' % (ss // 4 - 1), s); d = struct.unpack_from('<I', s, ss - 4)[0]
    fat = []
    for i in difat[:ndif]:
        fat += struct.unpack_from('<%dI' % (ss // 4), sec(i))

    def chain(i):
        out = bytearray()
        while i < 0xFFFFFFFA:
            out += sec(i); i = fat[i]
        return bytes(out)
    dirs = chain(dir0); ents = []
    for k in range(len(dirs) // 128):
        e = dirs[k * 128:(k + 1) * 128]
        nl = struct.unpack_from('<H', e, 64)[0]
        ents.append((e[:max(nl - 2, 0)].decode('utf-16le'), e[66], struct.unpack_from('<I', e, 116)[0],
                     struct.unpack_from('<I', e, 120)[0]))
    root = ents[0]; mstream = chain(root[2])
    mfat = []
    i = mfat0
    while i < 0xFFFFFFFA:
        mfat += struct.unpack_from('<%dI' % (ss // 4), sec(i)); i = fat[i]
    out = {}
    for nm, typ, st, sz in ents[1:]:
        if typ != 2:
            continue
        if sz < cutoff:
            data = bytearray(); i = st
            while i < 0xFFFFFFFA:
                data += mstream[i * mss:(i + 1) * mss]; i = mfat[i]
        else:
            data = chain(st)
        out[nm] = bytes(data[:sz])
    return out


def doc_text(b):
    """Word 6/95 일본어판(wIdent 0xA697): fcMin‥fcMac 에 글자마다 u16 LE — 0x100 이상은 SJIS 코드."""
    wd = ole_streams(b)['WordDocument']
    assert struct.unpack_from('<H', wd, 0)[0] == 0xA697
    fcMin, fcMac = struct.unpack_from('<II', wd, 0x18)
    out = []
    for (c,) in struct.iter_unpack('<H', wd[fcMin:fcMac - (fcMac - fcMin) % 2]):
        out.append(chr(c) if c < 0x100 else bytes([c >> 8, c & 0xFF]).decode('cp932', 'replace'))
    return ''.join(out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    t = doc_text(open(SRC, 'rb').read())
    t = t.replace('\r', '\n').replace('\x0b', '\n').replace('\x07', '\t').replace('\x0c', '\n')
    open(OUT, 'w', encoding='utf-8').write(t)
    print(len(t), '자 →', OUT)
