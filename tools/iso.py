# -*- coding: utf-8 -*-
r"""트랙 01 파일 바꿔 넣기(2026-10-19, 건담 외전 iso.py 에서) — 트랙 크기 그대로(뒤는 CD-DA 트랙 18개, /STxx.CDA 가 그 자리를 가리킴).
  원본: 마지막 데이터 파일(/FUROKU/POS4.BMP)이 LBA 81550 에서 끝, 트랙 01 = 81,700섹터 → 뒤 150섹터만 빈 자리.
  ★빈 자리 늘리기: 다시 구운 동영상(OPENING.CPK 78.0→62.0 MB · ST1.CPK 44.3→39.5 MB)은 디렉터리 크기를 실제 길이로 줄이고,
    원래 자리 뒤쪽 남는 섹터를 빈 자리로 쓴다(FILM 은 STAB 이 가리키는 곳까지만 읽음).
  규칙: 새 파일이 원래 섹터 수 안이면 제자리(남는 곳 0), 넘치면 빈 자리에 차례로 → 모자라면 빌드 실패.
        디렉터리 기록 LBA·크기(양 엔디안), 쓴 섹터는 헤더·EDC/ECC 새로(유나 리믹스 iso.sector). 끝에 되읽기 검산.
  from iso import patch; patch(dst, {'/SS/STG01.BIN': bytes, ...})
"""
import importlib.util, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc

_sp = importlib.util.spec_from_file_location('yuna_iso', r'C:\claude\project\yunaremix-kr-patch\tools\iso.py')
_y = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_y)
sector = _y.sector
FREE = 81550; TRACK = 81700


def sec(f, l):
    f.seek(l * 2352 + 16); return f.read(2048)


def records(f):
    pvd = sec(f, 16); out = []
    def walk(lba, size, pre):
        for k in range((size + 2047) // 2048):
            d = sec(f, lba + k); i = 0
            while i < 2048 and d[i]:
                L = d[i]; nm = d[i + 33:i + 33 + d[i + 32]]
                if nm not in (b'\0', b'\1'):
                    n = nm.decode('latin1').split(';')[0]
                    l2, s2 = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0]
                    if d[i + 25] & 2: walk(l2, s2, pre + n + '/')
                    else: out.append((pre + n, lba + k, i, l2, s2))
                i += L
    root = pvd[156:190]
    walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '/')
    return out


def carve(free, a, n):
    """빈 자리 목록에서 [a, a+n) 을 떼어 냄 — 빈 자리 안이어야 함"""
    for k, (s, e) in enumerate(free):
        if s <= a and a + n <= e:
            free[k:k + 1] = [x for x in ((s, a), (a + n, e)) if x[1] > x[0]]
            return
    raise SystemExit('고정 자리 %d+%d 가 빈 자리 밖: %s' % (a, n, free))


def patch(dst, files, log=print, fixed=None):
    """fixed = {이름: LBA} — ★빌드마다 위치가 바뀌면 옛 시험본 스테이트(게임이 부팅 때 읽어 둔 파일 위치)로 이어 할 때
       빈칸을 읽어 크래시(2026-10-19 2차 시험본) → 늘어난 파일은 고정 자리에"""
    fixed = fixed or {}
    src = disc.ROM
    assert os.path.getsize(src) == TRACK * 2352
    f = open(src, 'rb'); recs = {r[0]: r for r in records(f)}
    data_end = max(l + (s + 2047) // 2048 for n, _, _, l, s in recs.values() if not n.endswith('.CDA'))
    assert data_end == FREE, data_end
    secs = lambda n: (n + 2047) // 2048
    plan = {}; free = [(FREE, TRACK)]
    for name, data in files.items():                                  # 제자리 먼저 — 줄어든 파일의 남는 섹터는 빈 자리로
        _, dl, di, lba, size = recs[name]
        if secs(len(data)) <= secs(size):
            plan[name] = lba
            if secs(len(data)) < secs(size): free.append((lba + secs(len(data)), lba + secs(size)))
    for name, (lba, room) in fixed.items():
        need = secs(len(files[name]))
        assert name not in plan and need <= room, (name, need, room)
        carve(free, lba, room); plan[name] = lba
    for name, data in files.items():
        if name in plan: continue
        need = secs(len(data))
        for k, (a, b) in enumerate(free):
            if b - a >= need:
                plan[name] = a; free[k] = (a + need, b); break
        else:
            raise SystemExit('트랙 01 빈 자리 모자람: %s %d섹터 · 빈 자리 %s' % (name, need, free))
    with open(src, 'rb') as i, open(dst, 'wb') as o:
        while True:
            b = i.read(1 << 24)
            if not b: break
            o.write(b)
    with open(dst, 'r+b') as o:
        for name, data in files.items():
            lba = plan[name]
            for k in range(secs(len(data))):
                o.seek((lba + k) * 2352); o.write(sector(lba + k, data[k * 2048:(k + 1) * 2048].ljust(2048, b'\0')))
        for a, b in free:                                             # 빈 자리로 돌린 곳은 0 섹터(옛 동영상 꼬리 지움)
            if a >= FREE: continue
            for l in range(a, b):
                o.seek(l * 2352); o.write(sector(l, bytes(2048)))
        dirs = {}
        for name, data in files.items():
            _, dl, di, _, _ = recs[name]
            if dl not in dirs:
                o.seek(dl * 2352 + 16); dirs[dl] = bytearray(o.read(2048))
            d = dirs[dl]; lba = plan[name]
            struct.pack_into('<I', d, di + 2, lba); struct.pack_into('>I', d, di + 6, lba)
            struct.pack_into('<I', d, di + 10, len(data)); struct.pack_into('>I', d, di + 14, len(data))
        for dl, d in dirs.items():
            o.seek(dl * 2352); o.write(sector(dl, bytes(d)))
    g = disc.Disc(dst)                                                # 되읽기 검산
    for name, data in files.items():
        assert g.read(name) == data, name
    for name, (_, _, _, lba, size) in recs.items():                   # 안 바꾼 파일은 그대로
        if name not in files and not name.endswith('.CDA'):
            assert plan.get(name) is None
    for name in files:
        log('  %-18s LBA %6d → %6d · %d B' % (name, recs[name][3], plan[name], len(files[name])))
    log('트랙 01: 크기 그대로 %d섹터 · 바뀐 파일 %d · 남은 빈 자리 %s' % (TRACK, len(files), [(a, b - a) for a, b in free if b > a]))
