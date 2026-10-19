# -*- coding: utf-8 -*-
r"""타이틀 화면 로고 아래 가타카나 읽기 줄 «レイディアント シルバーガン» → «레이디언트 실버건» (2026-10-19)
  그림 = SS/TITLEBG.BIN: +0x18 팔레트 256색(u16) · +0x218 256색 8×8 칸 0x2A098 B(VRAM 0 에 그대로) · 뒤 = 맵.
  화면 NBG1 면 A(512×512, 2워드 맵 VRAM 0x40000) — 칸 번호는 타이틀 스테이트(work/mem/title)에서.
  · 지우기: 가타카나 = 회색 경사(0·6·5·4 밝은 획, 3·2·1 가장자리) → 밝은 획 1px 팽창을 주변에서 메움(cv2 inpaint) → 팔레트 가장 가까운 색.
  · 그리기: 나눔고딕 안티 글씨를 «지운 뒤 바탕»과 섞어 팔레트 가장 가까운 색(원본 가타카나처럼 부드러운 가장자리), 원래 줄 가운데·같은 높이.
  · ⛔여러 자리가 같이 쓰는 칸(검정 45번 등)은 바꾸면 안 됨 → 글꼴 크기·자간·위아래·좌우 위치를 훑어 공유 칸을 피하는 배치를 고름.
    피할 수 없는 칸은 안 쓰는 칸(0번 하나뿐 — 같은 내용 칸도 없음)으로 맵을 돌림.
  · 맵 = 파일 +0x2A098(머리 +0x14), 88칸 × 56줄 u16(값 = VRAM 글자 번호 = 칸×2), 줄·열 = 면 A 와 같음. 칸 = 0x218‥0x2A098 (2,682개).
  python tools/titlegfx.py   → 미리보기 work/gfx/prev_title.png(원본|새것, 실제 색 4배)
"""
import os, struct, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothic.ttf'
TEXT = '레이디언트 실버건'
OUTLINE = '--no-outline' not in sys.argv   # ✅B안(글자 둘레 1px 어두운 테두리) 하스피 선택 2026-10-19 — A안은 --no-outline
BOX = (255, 295, 215, 500)            # 면 A 안 (y0, y1, x0, x1) — 가타카나 줄을 둘러싼 곳
CHARS = 0x218; NCH = 0x2A098; MAP = 0x2A098; MW = 88; NCELL = 2682; FREE = [0]   # FREE = 안 쓰는 칸의 VRAM 글자 번호


def load():
    import vdp2render as V
    v, reg, cram = V.load('title')
    cells = V.render('title', 1, plane=0)[1]['cells']
    t = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'SS', 'TITLEBG.BIN'), 'rb').read())
    assert bytes(v[:NCH - 0x240]) == bytes(t[CHARS:CHARS + NCH - 0x240])
    return t, cells


def palette(t):
    p = np.frombuffer(bytes(t[0x18:0x218]), '>u2').astype(int)
    return np.stack([(p & 31) << 3, ((p >> 5) & 31) << 3, ((p >> 10) & 31) << 3], -1)


def plane(t, cells):
    idx = np.zeros((512, 512), int)
    for cy in range(64):
        for cx in range(64):
            o = CHARS + cells[cy, cx] * 0x20
            idx[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = np.frombuffer(bytes(t[o:o + 64]), np.uint8).reshape(8, 8)
    return idx


def nearest(pal, rgb):
    return ((rgb[..., None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)


def make(t, cells):
    pal = palette(t); idx = plane(t, cells)
    y0, y1, x0, x1 = BOX
    sub = idx[y0:y1, x0:x1]
    shared = shared_mask(cells)[y0:y1, x0:x1]
    # 가타카나 = 회색 경사 안티 글씨(0·6 흰색 → 5·4 회색 → 3·2·1 어두운 가) — 밝은 4·5·6·0 을 1px 넓혀 가장자리까지
    light = np.isin(sub, [0, 4, 5, 6])
    mask = (cv2.dilate(light.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & ~shared
    ys, xs = np.nonzero(light)
    top, bot, left, right = ys.min(), ys.max(), xs.min(), xs.max()
    rgb = pal[sub].astype(np.uint8)
    fill = cv2.inpaint(rgb[..., ::-1].copy(), mask.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)[..., ::-1].astype(int)
    bg = np.where(mask[..., None], fill, pal[sub])                         # 지운 뒤 바탕(실제 색)
    ers = sub.copy(); ers[mask] = nearest(pal, fill)[mask]
    # 지우고 나서 «완전 검정(255)»이 된 칸 = 공유 빈칸(90번)과 같은 그림 → 맵을 90 으로 돌리고 그 칸을 비워 재사용
    blankable = []
    for cy in range(y0 // 8, (y1 + 7) // 8):
        for cx in range(x0 // 8, (x1 + 7) // 8):
            ry, rx = cy * 8 - y0, cx * 8 - x0
            if ry < 0 or rx < 0 or ry + 8 > y1 - y0 or rx + 8 > x1 - x0: continue
            if not shared[ry, rx] and (ers[ry:ry + 8, rx:rx + 8] == 255).all() and int(cells[cy, cx]) != 90:
                blankable.append((cy, cx))
    h = bot - top + 1
    best = None
    dd = ImageDraw.Draw(Image.new('L', (1, 1)))
    # 원래 줄 가운데 고정(±4px) — 사진의 밝은 빛이 글자 사이에 걸리는 건 원본 그림 그대로(B안 테두리로 구분)
    for px in range(14, 24):
        F = ImageFont.truetype(FONT, px)
        bb = dd.textbbox((0, 0), TEXT, font=F); gh = bb[3] - bb[1]
        adv = [dd.textlength(c, font=F) for c in TEXT]
        for extra in np.arange(0, 4.5, 0.5):
            total = sum(adv) + extra * (len(TEXT) - 1)
            for dx in range(-4, 5, 2):
                for dy in range(-3, 4):
                    lay = Image.new('L', (x1 - x0, y1 - y0), 0); dr = ImageDraw.Draw(lay)
                    x = (left + right + 1) / 2 - total / 2 + dx
                    for c, a_ in zip(TEXT, adv):
                        dr.text((x, top + dy - bb[1] + (h - gh) // 2), c, font=F, fill=255); x += a_ + extra
                    cov = np.array(lay) / 255.0
                    drawn = cov > 0.12
                    if OUTLINE:
                        drawn = cv2.dilate(drawn.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
                    hy, hx = np.nonzero(shared & drawn)
                    bad = len(set(zip((hy + y0) // 8, (hx + x0) // 8)))           # 글씨가 닿는 공유 칸 수
                    dy_, dx_ = np.nonzero(drawn)
                    touched = set(zip((dy_ + y0) // 8, (dx_ + x0) // 8))
                    pool = len(FREE) + sum(1 for p in blankable if p not in touched)
                    score = (max(0, bad - pool), abs(gh - h), abs(total - 0.8 * (right - left + 1)) / 8, abs(dx) + abs(dy))
                    if best is None or score < best[0]:
                        best = (score, px, extra, dx, dy, cov, drawn)
    score, px, extra, dx, dy, cov, drawn = best
    assert score[0] == 0, ('공유 칸을 피하는 배치 없음', score)
    hy, hx = np.nonzero(shared & drawn)
    remap = sorted(set(zip((hy + y0) // 8, (hx + x0) // 8)))           # 글씨가 닿는 공유 칸 → 새 칸으로 돌림
    dy_, dx_ = np.nonzero(drawn)
    touched = set(zip((dy_ + y0) // 8, (dx_ + x0) // 8))
    blank = [p for p in blankable if p not in touched][:max(0, len(remap) - len(FREE))]
    slots = FREE + [int(cells[p]) for p in blank]
    assert len(remap) <= len(slots), '새 칸 모자람'
    medit = {p: 90 for p in blank}                                      # 맵 고침: 빈칸이 된 자리 → 90
    medit.update({p: slots[k] for k, p in enumerate(remap)})            # 글씨가 닿는 공유 자리 → 비운 칸
    for cy, cx in remap:
        shared[cy * 8 - y0:cy * 8 + 8 - y0, cx * 8 - x0:cx * 8 + 8 - x0] = False
    if OUTLINE:                                                             # B안: 글자 둘레 1px 어두운 테두리(밝은 사진 빛 위에서도 읽히게)
        ring = (drawn & (cov <= 0.12)).astype(float)
        bg = bg * (1 - 0.8 * ring[..., None]) + 8 * 0.8 * ring[..., None]
    col = cov[..., None] * 248 + (1 - cov[..., None]) * bg                  # 흰 글씨를 바탕에 섞음(안티)
    out_rgb = np.where(drawn[..., None], col, bg)
    new = sub.copy()
    ch = mask | drawn
    new[ch] = nearest(pal, out_rgb.astype(int))[ch]
    new[shared] = sub[shared]
    out = idx.copy(); out[y0:y1, x0:x1] = new
    return idx, out, pal, px, (extra, dx, dy, score), medit


def shared_mask(cells):
    import collections
    cnt = collections.Counter(int(c) for c in cells.ravel())
    m = np.zeros((512, 512), bool)
    for cy in range(64):
        for cx in range(64):
            if cnt[int(cells[cy, cx])] > 1: m[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = True
    return m


def changed_cells(idx, out, cells, medit=None):
    """→ ({VRAM 글자 번호: 64 B 그림}, 공유 칸 검사). medit = {(줄, 열): 새 글자 번호} — 90 이면 빈칸으로 돌린 자리(그림 안 씀)"""
    import collections
    medit = medit or {}
    cnt = collections.Counter(int(c) for c in cells.ravel())
    ch = {}
    for cy in range(64):
        for cx in range(64):
            a = idx[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]; b = out[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
            c = int(cells[cy, cx])
            if (cy, cx) in medit:
                if medit[(cy, cx)] == 90:
                    assert (b == 255).all(); continue
                c = medit[(cy, cx)]
            elif not (a != b).any():
                continue
            ch.setdefault(c, b.astype(np.uint8).tobytes())
            assert ch[c] == b.astype(np.uint8).tobytes(), ('같은 칸 다른 그림', c)
    freed = {v for v in medit.values() if v != 90}
    shared = {c: cnt[c] for c in ch if c not in freed and cnt[c] > 1}
    return ch, shared


def patch(t, ch, medit=None):
    """칸 그림 쓰기(키 = VRAM 글자 번호 = 칸×2) + 맵 고침(medit)"""
    t = bytearray(t)
    for (cy, cx), v in (medit or {}).items():
        o = MAP + (cy * MW + cx) * 2
        struct.pack_into('>H', t, o, v)
    for c, b in ch.items():
        t[CHARS + c * 0x20:CHARS + c * 0x20 + 64] = b
    return bytes(t)


def preview(idx, out, pal):
    y0, y1, x0, x1 = BOX
    a = pal[idx[y0 - 30:y1 + 10, x0 - 20:x1 + 10]].astype(np.uint8); b = pal[out[y0 - 30:y1 + 10, x0 - 20:x1 + 10]].astype(np.uint8)
    h, w = a.shape[:2]
    im = Image.new('RGB', (w * 4, h * 8 + 8), (60, 60, 60))
    im.paste(Image.fromarray(a).resize((w * 4, h * 4), Image.NEAREST), (0, 0))
    im.paste(Image.fromarray(b).resize((w * 4, h * 4), Image.NEAREST), (0, h * 4 + 8))
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    p = os.path.join(ROOT, 'work', 'gfx', 'prev_title_%s.png' % ('B' if OUTLINE else 'A')); im.save(p)
    full = Image.new('RGB', (704, 260))
    full.paste(Image.fromarray(pal[idx[150:280, 0:352]].astype(np.uint8)).resize((352, 130)), (0, 0))
    return p


def build():
    """빌드용: 고친 TITLEBG.BIN 바이트"""
    t, cells = load()
    idx, out, pal, px, extra, medit = make(t, cells)
    ch, shared = changed_cells(idx, out, cells, medit)
    assert not shared
    return patch(t, ch, medit)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    t, cells = load()
    idx, out, pal, px, extra, medit = make(t, cells)
    ch, shared = changed_cells(idx, out, cells, medit)
    print('맵 고친 자리', {k: v for k, v in medit.items()})
    # 되읽기: 고친 파일(칸+맵)로 다시 그려 미리보기와 같은지
    t2 = patch(t, ch, medit)
    m = np.frombuffer(bytes(t2[MAP:]), '>u2').astype(int).reshape(56, MW)
    c2 = cells.copy(); c2[:56, :64] = m[:, :64]
    assert (plane(t2, c2)[:448] == out[:448]).all(), '되읽기 다름'
    print('글꼴 %dpx · 자간 +%.1f · 좌우 %+d · 위아래 %+d · 점수 %s · 바뀐 칸 %d · 공유 칸 %s' % ((px,) + extra[:3] + (extra[3], len(ch), shared or '없음')))
    print('미리보기', preview(idx, out, pal))
    return ch, shared


if __name__ == '__main__':
    main()
