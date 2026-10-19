# -*- coding: utf-8 -*-
r"""데모(TRIAL RIDE MODE) 화면 아래 일본어 안내 «ソードを使えば □ この敵弾を消せる» → 한글 (2026-10-19)
  그림 = SS/SCRDAT01.BIN: +0 u32(크기) · +4 16색 8×8 칸 157개(칸 n = VRAM 글자 번호 0x3000+n) ·
         맵 = 32×32 쪽 둘(왼쪽 열 0‥31 @0x13A4, 오른쪽 32‥63 @0x1BA4, u16: 비트 15‥12 팔레트 · 11 세로 · 10 가로 뒤집기 · 9‥0 칸).
  화면 NBG0(스테이트 work/mem/demo1, 맵 VRAM 0x76000). 안내 줄 = 23·24행, 열 4‥18(«ソードを使えば») · 19‥21(□ 아이콘, 그대로) · 22‥39(«この敵弾を消せる»).
  · 원본 글씨 = 줄 안 행마다 색번호 고정(0‥8행 4 · 9‥10행 3 · 11‥12행 2 · 13‥15행 1, 테두리 없음) → 한글도 같은 규칙.
  · 칸: 이 줄만 쓰는 칸 53개 안에서 새로 배정(같은 그림 칸은 하나로, 빈 자리 = 0번 빈칸). 좌우 시작 위치를 몇 px 훑어 칸 수가 53 이하인 배치.
  · ⛔파일 0x1364‥0x13A4(칸 155·156 처럼 보이는 64 B)는 «팔레트»(CRAM 0x200 에 실림) — 2026-10-19 4·5차에서 여기에 글자를 써 화면 색이 다 깨짐.
    → 칸은 0‥154(155개)뿐. 빌드 때 팔레트·다른 자리 바이트가 원본과 같은지 검사.
  python tools/demogfx.py   → 미리보기 work/gfx/prev_demo.png(원본|새것, 스테이트 팔레트 4배 — 게임에선 주황으로 보임)
"""
import collections, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FONT = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.ttf'
LEFT, RIGHT = '소드를 쓰면', '이 적탄을 지울 수 있다'
ROWS = (23, 24); LCOLS = range(4, 19); RCOLS = range(22, 42)   # 오른쪽은 원래 39 열까지 → 한글이 6px 길어 41 열까지(원래 빈칸, 화면 44열 안)
CELLS = 4; MAPL = 0x13A4; MAPR = 0x1BA4; NCELL = 155; PAL = (0x1364, 0x13A4)
ROWCOL = [4] * 9 + [3] * 2 + [2] * 2 + [1] * 3


def src():
    return open(os.path.join(ROOT, 'work', 'disc', 'SS', 'SCRDAT01.BIN'), 'rb').read()


def eo(cy, cx):
    return (MAPL if cx < 32 else MAPR) + (cy * 32 + cx % 32) * 2


def ent(b, cy, cx):
    return struct.unpack_from('>H', b, eo(cy, cx))[0]


def cell(b, c):
    d = np.frombuffer(b[CELLS + c * 32:CELLS + c * 32 + 32], np.uint8)
    return np.stack([d >> 4, d & 15], 1).ravel().reshape(8, 8).astype(int)


def strip(lx, rx):
    """한글 줄 그림(16 × 8·42) — 색번호 그대로. lx = 왼쪽 문구 끝 x, rx = 오른쪽 문구 시작 x"""
    F = ImageFont.truetype(FONT, 14)
    im = Image.new('L', (42 * 8, 16), 0); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.text((lx - d.textlength(LEFT, font=F), 1), LEFT, font=F, fill=255)   # □ 앞에 붙여 오른쪽 맞춤
    d.text((rx, 1), RIGHT, font=F, fill=255)                              # □ 뒤에서 시작
    ink = np.array(im) >= 128
    if ink[:, :4 * 8].any() or ink[:, 19 * 8:22 * 8].any() or ink[:, 42 * 8 - 1:].any():
        return None
    px = np.zeros(ink.shape, int)
    for y in range(16):
        px[y][ink[y]] = ROWCOL[y]
    return px


def cells_of(px, pos):
    """자리마다 8×8 → {자리: 그림 바이트(빈칸이면 None)}"""
    out = {}
    for cy, cx in pos:
        r = (cy - ROWS[0]) * 8
        p = px[r:r + 8, cx * 8:cx * 8 + 8]
        out[(cy, cx)] = None if not p.any() else bytes(int(p[y, 2 * i]) << 4 | int(p[y, 2 * i + 1]) for y in range(8) for i in range(4))
    return out


def make(b):
    use = collections.defaultdict(list)
    for cy in range(32):
        for cx in range(64):
            use[ent(b, cy, cx) & 0x3FF].append((cy, cx))
    assert max(use) < NCELL, '맵이 팔레트 자리 칸을 가리킴'
    pos = [(cy, cx) for cy in ROWS for cx in list(LCOLS) + list(RCOLS)]
    line = {ent(b, cy, cx) & 0x3FF for cy, cx in pos} - {0}
    pool = sorted(c for c in line if all(p in pos for p in use[c]))
    assert not cell(b, 0).any(), '0번 칸이 빈칸이 아님'
    best = None
    for lx in range(19 * 8 - 12, 19 * 8 - 1):
        for rx in range(22 * 8, 22 * 8 + 8):
            px = strip(lx, rx)
            if px is None: continue
            cs = cells_of(px, pos)
            n = len({v for v in cs.values() if v})
            key = (n > len(pool), abs((19 * 8 - 6) - lx) + abs((22 * 8 + 2) - rx))   # 칸 수 안 → 원래 자리 가까이
            if best is None or key < best[0]:
                best = (key, n, cs, lx, rx)
    key, need, cs, lx, rx = best
    assert need <= len(pool), ('칸 모자람', need, len(pool))
    out = bytearray(b); slot = {}
    for (cy, cx), v in cs.items():
        if v is None:
            c = 0
        else:
            if v not in slot:
                slot[v] = pool[len(slot)]
                c = slot[v]; out[CELLS + c * 32:CELLS + c * 32 + 32] = v
            c = slot[v]
        struct.pack_into('>H', out, eo(cy, cx), c)
    for c in pool[len(slot):]:                                           # 남은 줄 칸은 0(어디서도 안 씀)
        out[CELLS + c * 32:CELLS + c * 32 + 32] = bytes(32)
    # 검사: 바뀐 바이트는 «이 줄 칸» 과 «이 줄 맵 자리» 안에서만 · 팔레트 그대로
    ok = set()
    for c in pool: ok |= set(range(CELLS + c * 32, CELLS + c * 32 + 32))
    for p in pos: ok |= {eo(*p), eo(*p) + 1}
    bad = [i for i in range(len(b)) if b[i] != out[i] and i not in ok]
    assert not bad, ('허용 밖 바이트 바뀜', [hex(i) for i in bad[:8]])
    assert out[PAL[0]:PAL[1]] == b[PAL[0]:PAL[1]]
    return bytes(out), need, len(pool), (lx, rx)


def render(b, cram):
    import vdp2render as V
    img = np.zeros((32, 352, 3), np.uint8)
    for r, cy in enumerate(range(22, 26)):
        for cx in range(44):
            w = ent(b, cy, cx); p = cell(b, w & 0x3FF)
            if (w >> 10) & 1: p = p[:, ::-1]
            if (w >> 11) & 1: p = p[::-1]
            col = V.rgb(cram[((w >> 12) * 16 + p) & 0x7FF]); col[p == 0] = 0
            img[r * 8:r * 8 + 8, cx * 8:cx * 8 + 8] = col
    return img


def build():
    return make(src())[0]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import vdp2render as V
    b = src(); out, need, pool, xy = make(b)
    assert len(out) == len(b)
    _, _, cram = V.load('demo1'); cram = cram.astype(np.uint16).byteswap().astype(int)
    a, n = render(b, cram), render(out, cram)
    im = Image.new('RGB', (352 * 4, 32 * 8 + 8), (60, 60, 60))
    im.paste(Image.fromarray(a).resize((352 * 4, 128), Image.NEAREST), (0, 0))
    im.paste(Image.fromarray(n).resize((352 * 4, 128), Image.NEAREST), (0, 136))
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    p = os.path.join(ROOT, 'work', 'gfx', 'prev_demo.png'); im.save(p)
    print('칸 %d/%d 사용 · 왼쪽 끝 x %d · 오른쪽 시작 x %d · 팔레트 그대로 · 미리보기 %s' % (need, pool, xy[0], xy[1], p))


if __name__ == '__main__':
    main()
