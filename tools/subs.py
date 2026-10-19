# -*- coding: utf-8 -*-
r"""게임 중 CD-DA 대사 자막 자료 (2026-10-19, 건담 외전 subs.py 에서 — 시계 = CD 블록 FAD, 글꼴 한 벌 공유)
  입력: work/text/cues.tsv 의 트랙 2‥19 쪽(시각 = INDEX 01 기준 초, tools/cues.py 가 부호 뒤 공백까지 정리).
  블롭(상주 자리 base 에 그대로 실림):
    +0  'RSUB'
    +4  u16 트랙 수 N · u16 0
    +8  u32 글꼴 주소(글자마다 18 B, glyphpack 꼴 12×12 1비트 — 모든 트랙이 한 벌 공유)
    +12 트랙 표[N] : u32 시작 FAD(INDEX 01) · u32 끝 FAD(다음 트랙 처음) · u32 묶음 주소(자막 없으면 0)
    묶음 = 건담 외전 DSUB 꼴 그대로(훅 그리기 코드 재사용):
          +0 'DSUB' · +4 u16 쪽 수 · +6 0 · +8 0(4 B) · +12 u16 글꼴 자리(= 글꼴 주소 − 묶음 주소) · +14 0
          +16 쪽 표[쪽 수](u16 t0, u16 t1 — 트랙 처음부터 섹터(1/75초), u16 쪽 자리(묶음 기준), u16 0)
    쪽:   glyphpack 꼴(u8 w8, u8 nrow, u8 c0, u8 글자 수, 글자마다 3 B — 글꼴 번호 9비트)
  python tools/subs.py   → 크기·쪽 수 보고(쓰기 없음)
"""
import csv, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import glyphpack as G

G.MAXW = 300
DIR = r'C:\claude\roms\ss\Radiant Silvergun (Japan)'
FIRST, LAST = 2, 19


def track_fads():
    """트랙 번호 → (INDEX 01 FAD, 다음 트랙 처음 FAD). bin 크기에서(트랙 2‥ = 앞 2초 pregap 포함) — /STxx.CDA LBA+150 과 같음"""
    out = {}; lba = 0; sizes = {}
    for t in range(1, LAST + 1):
        sizes[t] = os.path.getsize(os.path.join(DIR, 'Radiant Silvergun (Japan) (Track %02d).bin' % t)) // 2352
    for t in range(1, LAST + 1):
        if t >= FIRST:
            out[t] = (lba + 150 + 150, lba + sizes[t] + 150)
        lba += sizes[t]
    return out


def cues():
    out = {}
    with open(os.path.join(ROOT, 'work', 'text', 'cues.tsv'), encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            if r['track'].isdigit():
                out.setdefault(int(r['track']), []).append((float(r['start']), float(r['end']), r['kr']))
    return out


def check_glyphs(t):
    for c in t:
        if c != ' ' and not any(G.glyph(c)):
            raise SystemExit('글꼴에 없는 글자 %r — %s' % (c, t))


def pages_for(rows):
    """[(초, 초, 번역)] → [(t0초, t1초, [줄…])] — 한 쪽(두 줄)에 안 들어가면 글자 수 비율로 시간을 나눔"""
    out = []
    for s, e, ko in sorted(rows):
        check_glyphs(ko)
        pg = G.pages_of(ko)
        lens = [max(1, len(''.join(p).replace(' ', ''))) for p in pg]; tot = sum(lens); acc = 0
        for p, L in zip(pg, lens):
            t0 = s + (e - s) * acc / tot; acc += L
            out.append([t0, s + (e - s) * acc / tot, p])
    return out


def page_rec(gi, w8, nrow, chars):
    assert w8 * nrow <= 255 and w8 <= 40
    r = bytes([w8, nrow, (40 - w8) // 2, len(chars)])
    for c, x, ln in chars:
        r += bytes([gi[c] & 0xFF, x & 0xFF, (x >> 8) | ln << 1 | (gi[c] >> 8) << 2])
    return r + bytes(-len(r) % 4)


def blob(base):
    C = cues(); F = track_fads()
    tracks = list(range(FIRST, LAST + 1))
    pages = {t: pages_for(C.get(t, [])) for t in tracks}
    lay = {t: [G.layout(p) for _, _, p in pages[t]] for t in tracks}
    gl = []; gi = {}
    for t in tracks:
        for _, _, chars in lay[t]:
            for c, _, _ in chars:
                if c not in gi:
                    gi[c] = len(gl); gl.append(c)
    if len(gl) > 511:
        raise SystemExit('서로 다른 글자 %d > 511' % len(gl))
    head = 12 + 12 * len(tracks)
    body = bytearray(); bund = {}; fix = []
    for t in tracks:
        if not pages[t]:
            continue
        recs = [page_rec(gi, *l) for l in lay[t]]
        b0 = base + head + len(body)
        offs = []; o = 16 + 8 * len(recs)
        for r in recs:
            offs.append(o); o += len(r)
        tab = b''
        for (a, z, _), off in zip(pages[t], offs):
            tab += struct.pack('>HHHH', int(round(a * 75)), int(round(z * 75)), off, 0)
        fix.append(len(body) + 12)                                     # 글꼴 자리는 글꼴 위치가 정해진 뒤
        body += b'DSUB' + struct.pack('>HH', len(recs), 0) + bytes(4) + bytes(4) + tab + b''.join(recs)
        bund[t] = b0
    font = base + head + len(body)
    for f in fix:
        d = font - (base + head + f - 12)
        assert 0 < d < 0x10000, d
        struct.pack_into('>H', body, f, d)
    body += b''.join(G.gbytes(c) for c in gl)
    hdr = b'RSUB' + struct.pack('>HHI', len(tracks), 0, font)
    for t in tracks:
        hdr += struct.pack('>III', F[t][0], F[t][1], bund.get(t, 0))
    assert len(hdr) == head
    out = hdr + bytes(body)
    info = {'tracks': {t: len(pages[t]) for t in tracks if pages[t]}, 'glyphs': len(gl), 'size': len(out)}
    return out + bytes(-len(out) % 4), info


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    b, info = blob(0x060B3000)
    print('트랙별 쪽', info['tracks'])
    print('글자 %d · 블롭 %d B' % (info['glyphs'], info['size']))
