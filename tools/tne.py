# -*- coding: utf-8 -*-
r"""레이디언트 실버건 SS/TNE_*.BIN(SBL 음색 자료) 샘플 뽑기 (2026-10-19)
  머리 = u16 오프셋 표(믹서·VL·PEG·PLFO 4개 + 음색들) — 0xFFEF 끝.
  음색 = 4 B 머리(+2 = 층 수-1) + 층 0x20 B × n. 층 +0 시작음 +1 끝음 +2 u16(0x10 = PCM8B, 0x60 = 루프 방식, 하위 4비트 = SA 19:16)
    +4 SA(15:0, 파일 앞 기준) +6 LSA +8 LEA(샘플 수).
  python tools/tne.py [파일…] → work/tne/<파일>_<음색>_<층>.wav (22050 Hz 가정) + 목록
"""
import os
import struct
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'disc', 'SS')
OUT = os.path.join(ROOT, 'work', 'tne')


def parse(d):
    offs = []
    for i in range(0, 0x400, 2):
        v = struct.unpack_from('>H', d, i)[0]
        if v == 0xFFEF:
            break
        offs.append(v)
    voices = offs[4:]
    out = []
    lim = min([v for v in voices if v > voices[0]] + [len(d)])
    first = len(d)
    for vi, vo in enumerate(voices):
        if vo + 4 > len(d) or vo >= first:                          # 음색 표는 첫 샘플 앞까지
            break
        n = d[vo + 2] + 1
        for li in range(n):
            lo = vo + 4 + 0x20 * li
            if lo + 0x20 > len(d):
                break
            w0, sa, lsa, lea = struct.unpack_from('>HHHH', d, lo + 2)
            sa |= (w0 & 0xF) << 16
            if d[lo] > d[lo + 1] or lsa > lea or sa < lo:
                continue
            first = min(first, sa)
            out.append(dict(v=vi, l=li, off=lo, bit8=bool(w0 & 0x10), loop=(w0 >> 5) & 3, sa=sa, lsa=lsa, lea=lea))
    return out


def pcm(d, L):
    if L['bit8']:
        a = np.frombuffer(d[L['sa']:L['sa'] + L['lea']], np.int8).astype(np.int16) * 256
    else:
        a = np.frombuffer(d[L['sa']:L['sa'] + 2 * L['lea']], '>i2').astype(np.int16)
    return a


def main(names):
    os.makedirs(OUT, exist_ok=True)
    for nm in names:
        d = open(os.path.join(SRC, nm), 'rb').read()
        seen = set()
        for L in parse(d):
            key = (L['sa'], L['lea'], L['bit8'])
            if key in seen or L['lea'] < 4000 or L['sa'] + L['lea'] * (1 if L['bit8'] else 2) > len(d) or L['sa'] < 0x40:
                continue
            seen.add(key)
            a = pcm(d, L)
            p = os.path.join(OUT, '%s_%02d_%d.wav' % (nm[:-4], L['v'], L['l']))
            with wave.open(p, 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(a.astype('<i2').tobytes())
            print('%s v%02d l%d sa %X n %d %s loop %d' % (nm, L['v'], L['l'], L['sa'], L['lea'], '8bit' if L['bit8'] else '16bit', L['loop']))


if __name__ == '__main__':
    main(sys.argv[1:] or sorted(f for f in os.listdir(SRC) if f.startswith('TNE')))
