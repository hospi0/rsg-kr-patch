# -*- coding: utf-8 -*-
r"""동영상 자막 굽기 (2026-10-19, 쿠오바디스 2·블루 브레이커 moviesub 에서 — FILM 1.09 · cinepak 320×224 띠 2개 · 12fps)
  자막 = work/text/cues.tsv 의 OPENING(OPENING.CPK)·ST1(ST1.CPK) 쪽(tools/cues.py 가 만듦 — 부호 뒤 공백은 이미 뗌).
         + work/text/telop.tsv(영상에 구워진 장소·시각 안내 번역, OPENING 4개 — ST1·ENDING 은 구워진 글자 없음 확인 2026-10-19).
  시간: 읽을 시간(글자×0.15초 + 0.8초, 최소 1.2초)보다 짧으면 다음 자막 앞까지 늘림.
  글씨: 나눔고딕 Bold 14px 흰색 + 검은 1px 테두리, 화면 아래 가운데(줄 간격 17px), 폭 넘치면 띄어쓰기에서 두 줄로 접기(세 줄 금지).
  굽기: tools/movenc.py(자막 든 키 구간만, 구간마다 원래 바이트 이하) → work/kr/SS/<이름>.CPK (원본 크기, 0 채움 — 디스크 제자리)
  미리보기: work/movie/sub/<이름>_kr.mp4 (2배, 소리 포함)
  python tools/moviesub.py [OPENING ST1] [--nopreview]
"""
import csv, glob, os, shutil, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import filmcpk, movenc, rules

FFBIN = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX, LH, W, H = 14, 17, 320, 224
MAXW = W - 16
WORK = os.path.join(ROOT, 'work', 'movie')
MOVIES = {'OPENING': 'OPENING.CPK', 'ST1': 'ST1.CPK'}


def src(k):
    return os.path.join(ROOT, 'work', 'disc', 'SS', MOVIES[k])


def rows():
    out = {}
    with open(os.path.join(ROOT, 'work', 'text', 'cues.tsv'), encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            if r['track'] in MOVIES:
                out.setdefault(r['track'], []).append((float(r['start']), float(r['end']), [r['kr']]))
    # 영상에 구워진 일본어 장소·시각 안내(테롭) 번역 — work/text/telop.tsv, «\n» = 줄바꿈
    with open(os.path.join(ROOT, 'work', 'text', 'telop.tsv'), encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            out.setdefault(r['movie'], []).append(
                (float(r['start']), float(r['end']), [rules.squeeze(x) for x in r['kr'].split('\\n')]))
    for k in out:
        out[k].sort()
    return out


def need(lines):
    return max(sum(len(p) for p in lines) * 0.15 + 0.8, 1.2)


def events(rs, dur):
    ev = []
    for k, (s, e, lines) in enumerate(rs):
        nxt = rs[k + 1][0] if k + 1 < len(rs) else dur
        ev.append((s, min(max(e, s + need(lines)), nxt - 0.07, dur - 0.05), lines))
    return ev


def wrap(lines, F, d):
    out = []
    for ln in lines:
        if d.textlength(ln, font=F) <= MAXW:
            out.append(ln); continue
        ws = ln.split(' '); best = None
        for i in range(1, len(ws)):
            a, b = ' '.join(ws[:i]), ' '.join(ws[i:])
            la, lb = d.textlength(a, font=F), d.textlength(b, font=F)
            if la <= MAXW and lb <= MAXW and (best is None or max(la, lb) < best[0]):
                best = (max(la, lb), a, b)
        assert best, ('줄 넘침', ln)
        out += [best[1], best[2]]
    assert len(out) <= 2, ('세 줄 이상', out)
    return out


def plate(lines, F):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lines = wrap(lines, F, d)
    y = H - 13 - (len(lines) - 1) * LH
    for ln in lines:
        d.text((W / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0)); y += LH
    px = im.load()
    for yy in range(H):
        for xx in range(W):
            r, g, b, a = px[xx, yy]
            px[xx, yy] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)     # 반투명 없이(cinepak 번짐 줄임)
    return im


def frames(k):
    fr = os.path.join(WORK, 'frames', k)
    if not glob.glob(os.path.join(fr, 'f*.png')):
        os.makedirs(fr, exist_ok=True)
        subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', src(k), '-fps_mode', 'passthrough',
                        os.path.join(fr, 'f%05d.png')], check=True)
    return fr


def times(k):
    film = filmcpk.read(open(src(k), 'rb').read())
    v = [e for e in film['stab'] if e[2] != 0xFFFFFFFF]
    return [((e[2] & 0x7FFFFFFF) / film['base'], ((e[2] & 0x7FFFFFFF) + e[3]) / film['base']) for e in v]


def burn(k, ev, log):
    fr = frames(k); T = times(k)
    nf = len(glob.glob(os.path.join(fr, 'f*.png'))); assert nf == len(T), ('프레임 수 불일치', nf, len(T))
    kr = os.path.join(fr, 'kr')
    if os.path.isdir(kr):
        shutil.rmtree(kr)
    os.makedirs(kr)
    F = ImageFont.truetype(FONT, PX); done = 0
    for a, b, lines in ev:
        pl = plate(lines, F)
        for f, (t0, t1) in enumerate(T):
            if t0 < b and t1 > a and (min(t1, b) - max(t0, a)) >= 0.5 * (t1 - t0):
                p = os.path.join(kr, 'f%05d.png' % (f + 1))
                im = Image.open(p if os.path.exists(p) else os.path.join(fr, 'f%05d.png' % (f + 1))).convert('RGBA')
                im.alpha_composite(pl); im.convert('RGB').save(p); done += 1
    out = os.path.join(ROOT, 'work', 'kr', 'SS', MOVIES[k])
    movenc.reencode(src(k), fr, kr, out, os.path.getsize(src(k)), log=log)
    log('%s 프레임 %d/%d 에 자막 → %s' % (k, done, nf, out))
    return out


def preview(k, path):
    os.makedirs(os.path.join(WORK, 'sub'), exist_ok=True)
    subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', path,
                    '-vf', 'scale=%d:%d:flags=neighbor' % (W * 2, H * 2), '-c:v', 'libx264', '-crf', '16',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', os.path.join(WORK, 'sub', k + '_kr.mp4')],
                   check=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    allr = rows()
    names = [a for a in sys.argv[1:] if not a.startswith('--')] or sorted(allr)
    log = lambda *a: print(*a, flush=True)
    F = ImageFont.truetype(FONT, PX)
    for k in allr:                                                     # 먼저 전부 폭 검사
        for _, _, lines in allr[k]:
            plate(lines, F)
    for k in names:
        ev = events(allr[k], times(k)[-1][1])
        log('== %s 자막 %d개' % (k, len(ev)))
        out = burn(k, ev, log)
        if '--nopreview' not in sys.argv:
            preview(k, out)
    log('끝')


if __name__ == '__main__':
    main()
