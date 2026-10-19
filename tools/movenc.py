# -*- coding: utf-8 -*-
r"""(쿠오바디스 2 tools/movenc.py 에서 2026-10-19) 자막 덮은 프레임이 든 키 구간(GOP)만 cinepak 으로 다시 굽고 FILM 을 다시 묶는다.
  레이디언트 실버건 = 320×224 · 띠 2개(112줄씩) · 12fps(기준 600, 프레임마다 50) · OPENING 3,628 중 키 200 · ST1 1,907 중 키 176.
  구간마다 ffmpeg cinepak(띠 1개, 첫 프레임만 키) → 새턴식(filmcpk.to_saturn) → 원래 구간 바이트 이하가 되도록 global_quality 사다리.
  ★구간마다 원래 바이트 이하(빚 넘기기 금지 — 1초 데이터량이 원본 최대를 넘으면 실기 끊김 위험). 소리 조각·나머지 구간은 원본 그대로.
"""
import glob, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import filmcpk

FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
STRIPS = 2
TMP = os.path.join(ROOT, 'work', 'movie', 'sub', '_gop')
LADDER = (0, 1000, 2000, 4000, 7000, 12000, 20000, 35000, 60000, 100000, 200000, 400000, 800000)


def encode(frames, q):
    if os.path.isdir(TMP):
        for f in glob.glob(os.path.join(TMP, '*')):
            os.remove(f)
    os.makedirs(TMP, exist_ok=True)
    for i, p in enumerate(frames):
        shutil.copyfile(p, os.path.join(TMP, 'g%05d.png' % (i + 1)))
    avi = os.path.join(TMP, 'o.avi')
    subprocess.run([FF, '-v', 'error', '-y', '-framerate', '12', '-i', os.path.join(TMP, 'g%05d.png'),
                    '-c:v', 'cinepak', '-min_strips', str(STRIPS), '-max_strips', str(STRIPS), '-max_extra_cb_iterations', '4',
                    '-g', '9999'] + (['-global_quality', str(q)] if q else []) + [avi], check=True)
    pk = filmcpk.avi_packets(open(avi, 'rb').read())
    assert len(pk) == len(frames), (len(pk), len(frames))
    return [filmcpk.to_saturn(p, i == 0) for i, p in enumerate(pk)]


def reencode(src, fr, kr, out, room, log=print):
    film = filmcpk.read(open(src, 'rb').read())
    vid = [i for i, e in enumerate(film['stab']) if e[2] != 0xFFFFFFFF]
    key = [k for k, i in enumerate(vid) if not film['stab'][i][2] & 0x80000000]
    changed = {int(os.path.basename(p)[1:6]) - 1 for p in glob.glob(os.path.join(kr, 'f*.png'))}
    gops = list(zip(key, key[1:] + [len(vid)]))
    chunks = list(film['chunks']); infos = [e[2] for e in film['stab']]
    n_re = debt = 0
    for a, b in gops:
        if not any(a <= f < b for f in changed): continue
        frames = [os.path.join(kr, 'f%05d.png' % (f + 1)) if os.path.exists(os.path.join(kr, 'f%05d.png' % (f + 1))) else os.path.join(fr, 'f%05d.png' % (f + 1)) for f in range(a, b)]
        budget = sum(len(film['chunks'][vid[f]]) for f in range(a, b))
        for q in LADDER:
            new = encode(frames, q)
            if sum(map(len, new)) <= budget: break
        else:
            over = sum(map(len, new)) - budget; debt += over
            log('  ⚠구간 %d‥%d 넘침 %d B' % (a + 1, b, over))
        for f, c in zip(range(a, b), new):
            chunks[vid[f]] = c
            t = film['stab'][vid[f]][2] & 0x7FFFFFFF
            infos[vid[f]] = t if f == a else t | 0x80000000
        n_re += 1
    assert all(len(c) % 4 == 0 for c in chunks), '4 바이트 정렬 아님'
    data = filmcpk.write(film, chunks, infos)
    assert len(data) <= room, ('자리 초과', len(data), room)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(data + bytes(room - len(data)))
    log('다시 구운 구간 %d/%d · %d B (원본 %d)%s' % (n_re, len(gops), len(data), os.path.getsize(src), ' ⚠넘침 합 %d' % debt if debt else ''))
    return len(data)
