# -*- coding: utf-8 -*-
r"""레이디언트 실버건 한글 자막 빌드(2026-10-19)
  ① 0BIOS.BIN: 처리기 리터럴 3개 → 상주 감싸개 · END 견본 리터럴 → TPL (크기 그대로, hook.patch_0bios)
  ② SS/STG01‥05.BIN: 0x37000 까지 0 채움 + 본체(코드·자막 자료) → 0x060B3000 (hook.patch_stg)
  ⑥ 데모 SS/SCRDAT01.BIN: TRIAL RIDE 아래 안내 «ソードを使えば □ この敵弾を消せる» → 한글(demogfx, 크기 그대로)
  ⑦ 아케이드 모드 = /STV/ 폴더: TITLEBG·SCRDAT01 은 SS 와 같은 파일이라 같은 결과
  ⑤ 타이틀 SS/TITLEBG.BIN: 로고 아래 가타카나 읽기 줄 → «레이디언트 실버건»(titlegfx, 크기 그대로)
  ③ 동영상 SS/OPENING.CPK·ST1.CPK: work/kr/SS/(먼저 python tools/moviesub.py) — 실제 길이로(뒤 0 채움 버림 → 빈 자리)
  ④ 디스크: iso.patch(트랙 01 크기 그대로) → work/out/…(Track 01).bin
  python tools/build.py            → 계획·검사만(디스크 안 씀)
  python tools/build.py --write    → work/out 에 트랙 01 쓰기
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc, filmcpk, hook, subs, titlegfx, demogfx

STGS = ['/SS/STG0%d.BIN' % i for i in range(1, 6)]
MOVIES = ['/SS/OPENING.CPK', '/SS/ST1.CPK']
# ★늘어난 스테이지 파일은 고정 자리(오프닝 영상 원래 자리 LBA 71‥38154 의 끝쪽, 파일마다 130섹터) —
#   빌드마다 위치가 바뀌면 옛 시험본 스테이트로 이어 할 때 게임이 부팅 때 읽어 둔 옛 위치(빈칸)를 읽어 크래시(2026-10-19)
SLOT = 130; SLOT0 = 38155 - SLOT * len(STGS)
FIXED = {s: (SLOT0 + SLOT * k, SLOT) for k, s in enumerate(STGS)}
OUT = os.path.join(ROOT, 'work', 'out', 'Radiant Silvergun (Japan) (Track 01).bin')


def film_len(d):
    """다시 구운 FILM 의 실제 길이(머리 + STAB 이 가리키는 끝) — 뒤 0 채움 버림"""
    f = filmcpk.read(d)
    return f['hl'] + max(e[0] + e[1] for e in f['stab'])


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    D = disc.Disc()
    sb, info = subs.blob(hook.SUBS)
    blk, lab = hook.block(sb)
    b0, rlab = hook.patch_0bios(D.read('/0BIOS.BIN'))
    files = {'/0BIOS.BIN': b0}
    tb = titlegfx.build(); assert len(tb) == len(D.read('/SS/TITLEBG.BIN'))
    files['/SS/TITLEBG.BIN'] = tb
    dm = demogfx.build(); assert len(dm) == len(D.read('/SS/SCRDAT01.BIN'))
    files['/SS/SCRDAT01.BIN'] = dm
    # ★아케이드 모드는 /STV/ 폴더를 읽음(2026-10-19 하스피: 아케이드로 바꾸니 타이틀이 일본어) — 두 파일은 SS 와 바이트까지 같아 같은 결과를 넣음
    for n, d in (('TITLEBG.BIN', tb), ('SCRDAT01.BIN', dm)):
        assert D.read('/STV/' + n) == D.read('/SS/' + n)
        files['/STV/' + n] = d
    for s in STGS:
        files[s] = hook.patch_stg(D.read(s), blk)
    for mv in MOVIES:
        d = open(os.path.join(ROOT, 'work', 'kr', 'SS', mv.split('/')[-1]), 'rb').read()
        n = film_len(d); assert not any(d[n:]), mv
        files[mv] = d[:n]
    print('① 자막 %d트랙 %d쪽 · 글자 %d · 본체 %d B(0x%08X‥0x%08X) · 상주 감싸개 %s' % (
        len(info['tracks']), sum(info['tracks'].values()), info['glyphs'], len(blk), hook.BLOCK, hook.BLOCK + len(blk),
        {k: hex(v) for k, v in rlab.items() if k in ('rvbi', 'rvin', 'rdmae')}))
    for s in STGS:
        print('② %s %d → %d B' % (s, len(D.read(s)), len(files[s])))
    for mv in MOVIES:
        print('③ %s %d → %d B' % (mv, len(D.read(mv)), len(files[mv])))
    if '--write' in sys.argv:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        import iso
        assert 71 + (len(files['/SS/OPENING.CPK']) + 2047) // 2048 <= SLOT0, '오프닝이 고정 자리를 침범'
        iso.patch(OUT, files, fixed=FIXED)
        print('→', OUT)
    else:
        print('(계획만 — 쓰려면 --write)')


if __name__ == '__main__':
    main()
