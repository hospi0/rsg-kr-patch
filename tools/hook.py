# -*- coding: utf-8 -*-
r"""레이디언트 실버건 CD-DA 대사 자막 훅(2026-10-19, 건담 외전 I hook.py(VDP1 스프라이트판) 를 옮김)
  · SGL 처리기 = 건담 외전과 같은 코드(위치만 다름) — VBlank-OUT·VBlank-IN·DMA 끝 등록 리터럴을 «상주 감싸개»로 돌림.
  · 상주 감싸개(RESI 0x06042C00 — 부팅 설치기가 복사, 아래 설명): 원래 처리기 부른 뒤 BLOCK 머리 'RSCD' 와 끝 표식이
    둘 다 맞을 때만 본체로 점프. 본체가 없으면(타이틀·동영상 등) 아무것도 안 함.
  · 본체+자막 자료 BLOCK = 0x060B3000: 스테이지 파일 STGxx.BIN(0x0607C000 적재, 파일 크기만큼 통째 읽기)을 0x37000 까지 0 채움 뒤에 붙임.
    (STG03 BSS ~0x060B0430·ESP 0x060B1E00 < BLOCK < 0BIOS 0x060B9000, 스테이트 7장 모두 0)
  · 시계: CD 블록 CR1(0x25890018) 상태 아래 4비트 3 = PLAY 일 때 FAD = (CR3 & 0xFF) << 16 | CR4.
          트랙 표(subs.blob)에서 시작 ≤ FAD < 끝 인 트랙 → t = FAD − 시작(섹터 1/75초) → 쪽.
  · 그림: 1비트 버퍼에 찍기(버닝 레인저 stamp) → 4비트 색 뱅크 그림(0 투명 · 0xC 검정 테두리 · 0xD 흰 글자)을 VDP1 0x8000
          (0x6000‥0xDFFF = 부팅 채움 무늬 5555/AAAA, 7장 모두 같고 아무 명령도 안 가리킴 — 명령표는 0x6000 앞까지만 자람).
  · 명령: 보통 스프라이트 PMOD 0x0080(색 뱅크 4비트·끝 코드 끔) · COLR 0x67F0 → 화소 0x67FC/0x67FD.
          ★스프라이트 종류가 장면마다 3/5(SPCTL 0x1423/0x1425): 종류 3 = 비트 14‥13 → S3, 종류 5 = 비트 14‥12 → S6
          → 자막 켜진 동안 PRISB 위 바이트(S3)·PRISD 아래 바이트(S6) = 7(레지스터만 — SGL 이 VBlank-IN 에 사본을 DMA 하므로 VBlank-IN 뒤 다시).
          좌표는 게임 지역 좌표(176,112 — 화면 352×224) 기준 → XA = −w8·4, YA = 112 − nrow·8 − 4.
          매 VBI 뒤 명령표(0x25C00000)를 END 까지 따라가 그 칸만 «건너뛰고 점프(0x5000) → 우리 칸 0x7000(명령+END)». 꺼지면 END 로.
  · ★END 견본: SGL 간접 DMA 표의 마지막 항목(30 B, 원래 0x060069E6)을 가리키는 리터럴 0x06006A00 → 우리 견본 TPL(0x06042D00).
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sh2asm import A

mov = lambda m, n: 0x6003 | n << 8 | m << 4
ldb = lambda m, n: 0x6000 | n << 8 | m << 4
ldbp = lambda m, n: 0x6004 | n << 8 | m << 4
stb = lambda m, n: 0x2000 | n << 8 | m << 4
ldb0 = lambda m, d: 0x8400 | m << 4 | d
stb0 = lambda n, d: 0x8000 | n << 4 | d
exb = lambda m, n: 0x600C | n << 8 | m << 4
exw = lambda m, n: 0x600D | n << 8 | m << 4
OR = lambda m, n: 0x200B | n << 8 | m << 4
AND = lambda m, n: 0x2009 | n << 8 | m << 4
ADD = lambda m, n: 0x300C | n << 8 | m << 4
SUB = lambda m, n: 0x3008 | n << 8 | m << 4
CMPHS = lambda m, n: 0x3002 | n << 8 | m << 4          # n >= m (부호 없음) → T
addi = lambda n, i: 0x7000 | n << 8 | (i & 0xFF)
movi = lambda n, i: 0xE000 | n << 8 | (i & 0xFF)
shll = lambda n: 0x4000 | n << 8; shlr = lambda n: 0x4001 | n << 8
shll2 = lambda n: 0x4008 | n << 8; shlr2 = lambda n: 0x4009 | n << 8
shll8 = lambda n: 0x4018 | n << 8; shlr8 = lambda n: 0x4019 | n << 8
shll16 = lambda n: 0x4028 | n << 8; shlr16 = lambda n: 0x4029 | n << 8
dt = lambda n: 0x4010 | n << 8
push = lambda m: 0x2F06 | m << 4; pop = lambda n: 0x60F6 | n << 8

LOAD = 0x06003000                         # 0BIOS.BIN 적재 주소
# ★상주 자리(2026-10-19 6차 «적 공격 때 그래픽 깨짐» 뒤 옮김):
#   ⛔옛 자리 0x06003CA0 = 주변기기 자료 버퍼(포인터 0x06003C7C, 0x200 B) 안 · ⛔옛 TPL 0x06015F40 = SGL 이벤트 칸 배열 안
#     → 적이 공격 효과 이벤트를 그 칸에 잡으면 이벤트 자료가 «END 견본»으로 VDP1 명령표 끝에 DMA 돼 쓰레기 다각형(흰 막대·초록 선).
#   → 0x06042C00‥0x06043000: BSS 끝(0x0604227C, = sbrk 힙 시작 — 힙 포인터 0x0601AE64 는 스테이트 15장 모두 0, 한 번도 안 씀)과
#     GAME.BIN(0x06043000) 사이, 파일·스테이트 15장 모두 0, 참조 없음. 힙이 조금 쓰여도 안 닿게 위쪽 1 KB 만.
#   어느 파일에도 안 실리므로 «부팅 설치기» BOOT 가 시작 코드의 main 호출(리터럴 0x0600B988 = 0x060082F0)을 가로채
#   0BIOS 파일 안 IMG(주변기기 버퍼 자리 — 부팅 때만 필요, 뒤에 덮여도 됨)를 RESI 로 복사한 뒤 main 으로 점프.
RESI = 0x06042C00; TPL = 0x06042D00; RESI_END = 0x06043000                  # 감싸개 ≤ 0x100 B 바로 뒤 TPL(32 B)
BOOT = 0x06003D00; BOOT_END = 0x06003E7C                         # 설치기 + 상주 그림 원본(파일 0 자리)
MAIN, MAIN_LIT = 0x060082F0, 0x0600B988
VBI, VBI_LIT = 0x0600593E, 0x06005B50
VIN, VIN_LIT = 0x060057E6, 0x06005B4C
DMAE, DMAE_LIT = 0x060057D4, 0x06005B5C
TPL_LIT, TPL_OLD = 0x06006A00, 0x860069E6

BLOCK = 0x060B3000; BLOCK_END = 0x060B9000
STG_PAD = BLOCK - 0x0607C000              # STGxx.BIN 을 이만큼 0 채운 뒤 BLOCK
MAGIC = 0x52534344                        # 'RSCD'
CODE = BLOCK + 0x20                       # 머리: +0 'RSCD' · +4 끝 표식 주소 · +8 vbi · +12 vin · +16 dmae
DATA = BLOCK + 0x800                      # 변수·명령
BUF = BLOCK + 0x900; BSTR = 52            # 1비트 쪽 버퍼 52 B × 34행
SUBS = BLOCK + 0x1000                     # subs.blob('RSUB')

CR1 = 0x25890018                          # CR2 +4 · CR3 +8 · CR4 +12
LIST = 0x25C00000
TEX = 0x25C08000; TEXA = (TEX & 0x7FFFF) // 8
OWN = 0x25C07000; OWNL = (OWN & 0x7FFFF) // 8
COLR = 0x6000 | 0x7F0                     # 색 뱅크 → 0x67FC(테두리)·0x67FD(글자)
CRAM_BK = 0x25F00000 + 0x7FC * 2
PRISB = 0x25F800F2; PRISD = 0x25F800F6; SHADOW = 0x060FFCC0
OFFN = 6                                  # «없음»이 6프레임 연달아야 끔(건담 외전 반짝임 대책)


def data_part():
    data = bytearray(); lab = {}
    def put(name, b):
        nonlocal data
        data += bytes(-len(data) % 4); lab[name] = DATA + len(data); data += b
    put('cur', bytes(4)); put('offc', bytes(4)); put('pay', bytes(4))
    put('cmd', struct.pack('>16H', 0x0000, 0, 0x0080, COLR, TEXA, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    assert DATA + len(data) <= BUF
    return bytes(data), lab


def resident():
    """상주 자리 RESI 에 실릴 감싸개 3개 → (코드, 라벨)"""
    a = A(RESI); W = a.w
    for name, orig, slot in (('rvbi', VBI, 2), ('rvin', VIN, 3), ('rdmae', DMAE, 4)):
        a.L(name); W(0x4F22, 0x4F02, 0x4F12)                          # PR·MACH·MACL(그리기에 mul)
        a.ld(0, orig); W(0x400B, 0x0009)
        a.ld(1, BLOCK); W(0x6012); a.ld(2, MAGIC); W(0x3020); a.br('bf', name + 'x')
        W(0x5311, 0x6032, 0x3020); a.br('bf', name + 'x')            # 끝 표식(머리 +4 가 가리킴)도 맞아야
        W(0x5010 | slot, 0x400B, 0x0009)
        a.L(name + 'x'); W(0x4F16, 0x4F06, 0x4F26, 0x000B, 0x0009)
    code = a.build()
    assert RESI + len(code) <= TPL, hex(RESI + len(code))
    return code, a.lab


def image():
    """RESI‥TPL+32 에 복사될 그림: 감싸개 + 0 + TPL(처음 = END)"""
    res, rlab = resident()
    img = bytearray(TPL + 32 - RESI)
    img[:len(res)] = res
    img[TPL - RESI:TPL - RESI + 2] = b'\x80\x00'
    return bytes(img), rlab


def boot():
    """부팅 설치기: IMG(설치기 바로 뒤) → RESI 로 복사 후 main 으로 jmp(PR 그대로 → main 은 원래 호출자에게 돌아감)"""
    img, _ = image()
    n = len(img) // 4
    a = A(BOOT); W = a.w
    a.ld(1, 'img'); a.ld(2, RESI); a.ld(3, n)
    a.L('cp'); W(0x6016, 0x2202, addi(2, 4), dt(3)); a.br('bf', 'cp')       # mov.l @r1+,r0 · mov.l r0,@r2
    a.ld(0, MAIN); W(0x402B, 0x0009)                                       # jmp @r0
    a.lab['img'] = BOOT                                                    # 임시(크기만 재기)
    code0 = a.build()
    a.lab['img'] = BOOT + (len(code0) + 3) // 4 * 4                         # 리터럴 풀 뒤(같은 크기로 다시 조립)
    code = a.build()
    assert len(code) == len(code0)
    out = code + bytes(a.lab['img'] - BOOT - len(code)) + img
    assert BOOT + len(out) <= BOOT_END, hex(BOOT + len(out))
    return out


def assemble(end_magic_addr):
    data, dlab = data_part()
    a = A(CODE); a.lab.update(dlab); W = a.w
    # ---- sub(VBlank-OUT 뒤) ----
    a.L('sub'); W(0x4F22)
    a.ld(1, CR1); W(0x6011, shlr8(0), 0xC90F, 0x8803); a.br('bf', 'none')     # 상태 아래 4비트 3 = PLAY
    W(0x8514, 0xC9FF, shll16(0), mov(0, 3), 0x8516, exw(0, 0), OR(0, 3))       # r3 = FAD
    a.ld(5, SUBS); W(0x8552, exw(0, 6), addi(5, 12))                           # r6 = 트랙 수, r5 = 트랙 표
    a.L('tl'); W(0x6252, CMPHS(2, 3)); a.br('bf', 'tn')                       # FAD ≥ 시작
    W(0x5051, CMPHS(0, 3)); a.br('bt', 'tn')                                  # FAD ≥ 끝 → 다음
    W(0x5452, 0x2448); a.br('bt', 'none')                                     # 묶음 없음
    W(SUB(2, 3)); a.br('bra', 'got'); W(0x0009)                               # r3 = t(섹터)
    a.L('tn'); W(addi(5, 12), dt(6)); a.br('bf', 'tl')
    a.br('bra', 'none'); W(0x0009)
    a.L('got'); a.ld(2, 'pay'); W(0x2242)
    W(0x8542, exw(0, 6)); W(mov(4, 1), addi(1, 16))                    # r6 = 쪽 수, r1 = 쪽 표
    W(0x2668); a.br('bt', 'none')
    a.L('lp'); W(0x6015, exw(0, 0), 0x3303); a.br('bf', 'nx')               # t ≥ t0
    W(0x6011, exw(0, 0), 0x3037); a.br('bf', 'nx')                          # t1 > t
    W(0x8511, exw(0, 5), ADD(4, 5)); a.ld(1, 'offc'); W(movi(0, 0), 0x2102); a.br('bra', 'have'); W(0x0009)
    a.L('nx'); W(addi(1, 6), dt(6)); a.br('bf', 'lp')
    a.L('none'); a.ld(1, 'offc'); W(0x6012, addi(0, 1), 0x2102, movi(2, OFFN), 0x3023); a.br('bt', 'nz')
    a.ld(1, 'cur'); W(0x6512); a.br('bra', 'have'); W(0x0009)
    a.L('nz'); W(movi(5, 0))
    a.L('have'); a.ld(1, 'cur'); W(0x6012, 0x3050); a.br('bt', 'same')
    W(0x2152, 0x2558); a.br('bt', 'off')
    a.br('bsr', 'draw'); W(mov(5, 1))
    a.L('on')
    a.ld(1, CRAM_BK); a.ld(0, 0x00007FFF); W(0x2102)                  # 0x7FC 검정 · 0x7FD 흰색
    a.br('bsr', 'prio'); W(0x0009)
    a.br('bsr', 'ins'); W(0x0009)
    a.br('bra', 'ret'); W(0x0009)
    a.L('same'); W(0x2558); a.br('bf', 'on')
    a.L('off'); a.br('bsr', 'unins'); W(0x0009)
    a.L('ret'); W(0x4F26, 0x000B, 0x0009)
    # ---- prio: 레지스터만 S3(PRISB 위)·S6(PRISD 아래) = 7, 나머지 바이트는 사본 값 ----
    a.L('prio'); a.ld(1, SHADOW + 0xF2); W(0x6011, 0xC9FF, movi(2, 7), shll8(2), OR(2, 0)); a.ld(1, PRISB); W(0x2101)
    a.ld(1, SHADOW + 0xF6); W(0x6011, shlr8(0), shll8(0), 0xCB07); a.ld(1, PRISD); W(0x2101)
    W(0x000B, 0x0009)
    # ---- walk: VDP1 이 읽는 순서대로 따라가 END 또는 우리 점프 칸 → r1(못 찾으면 0). r0‥r3 만 씀 ----
    a.L('walk'); a.ld(1, LIST); a.ld(3, 2048)
    a.L('wl'); W(0x6011, exw(0, 0)); a.ld(2, 0x8000); W(0x3022); a.br('bt', 'wret')          # END(비트 15)
    a.ld(2, 0x5000); W(0x3020); a.br('bf', 'wjp')
    W(0x8511, exw(0, 0)); a.ld(2, OWNL); W(0x3020); a.br('bt', 'wret')                       # 우리 점프
    W(0x6011, exw(0, 0))
    a.L('wjp'); W(shlr8(0), shlr2(0), shlr2(0), 0xC903, 0x8801); a.br('bf', 'wnx')           # 점프 지정(1·5 → 아래 3비트 1)
    W(0x8511, exw(0, 0), shll2(0), shll(0)); a.ld(2, LIST); W(ADD(2, 0), mov(0, 1)); a.br('bra', 'wdt'); W(0x0009)
    a.L('wnx'); W(addi(1, 32))
    a.L('wdt'); W(dt(3)); a.br('bf', 'wl')
    W(movi(1, 0))
    a.L('wret'); W(0x000B, 0x0009)
    # ---- ins: 찾은 칸을 «건너뛰고 점프 → 우리 칸» + 우리 칸(명령·END) ----
    a.L('ins'); W(0x4F22)
    a.ld(1, TPL); a.ld(0, 0x5000); W(0x2101); a.ld(0, OWNL); W(0x8111)   # 견본 = 우리 점프(다음 DMA 부터 게임이 써 넣음)
    a.br('bsr', 'walk'); W(0x0009)
    W(0x2118); a.br('bt', 'iret')
    a.ld(0, 0x5000); W(0x2101); a.ld(0, OWNL); W(0x8111)
    a.ld(1, OWN); a.ld(2, 'cmd'); W(movi(3, 8))
    a.L('ic'); W(0x6026, 0x2102, addi(1, 4), dt(3)); a.br('bf', 'ic')
    a.ld(0, 0x8000); W(0x2101)
    a.L('iret'); W(0x4F26, 0x000B, 0x0009)
    # ---- unins: 우리 점프 칸을 END 로 ----
    a.L('unins'); W(0x4F22)
    a.ld(1, TPL); a.ld(0, 0x8000); W(0x2101); W(movi(0, 0), 0x8111)      # 견본 = END
    a.br('bsr', 'walk'); W(0x0009)
    W(0x2118); a.br('bt', 'uret')
    W(0x6011, exw(0, 0)); a.ld(2, 0x5000); W(0x3020); a.br('bf', 'uret')
    a.ld(0, 0x8000); W(0x2101)
    a.L('uret'); W(0x4F26, 0x000B, 0x0009)
    # ---- vin(VBlank-IN 뒤): 레지스터 DMA 가 사본으로 되돌린 우선순위를 다시 ----
    a.L('vin'); a.ld(1, 'cur'); W(0x6012, 0x2008); a.br('bt', 'vret')
    a.br('bra', 'prio'); W(0x0009)
    a.L('vret'); W(0x000B, 0x0009)
    # ---- dmae(DMA 끝 뒤): 자막이 켜져 있으면 점프 다시(명령표 DMA 직후·그리기 전) ----
    a.L('dmae'); a.ld(1, 'cur'); W(0x6012, 0x2008); a.br('bt', 'vret')
    a.br('bra', 'ins'); W(0x0009)
    # ---- draw(r1 = 쪽) — 건담 외전 그대로, 마지막 화소 쓰기만 4비트 ----
    a.L('draw')
    W(0x4F22, push(1)); W(*[push(r) for r in range(8, 15)])
    W(0x58F7)
    a.ld(2, BUF); a.ld(3, BSTR * 34 // 4); W(movi(0, 0))
    a.L('cb'); W(0x2202, addi(2, 4), dt(3)); a.br('bf', 'cb')
    a.ld(9, 'pay'); W(0x6992)                                          # r9 = 지금 묶음
    W(0x8596, exw(0, 0), ADD(0, 9))
    W(ldb0(8, 3), exb(0, 10), mov(8, 11), addi(11, 4))
    W(0x2AA8); a.br('bt', 'chd')
    a.L('ch')
    W(ldbp(11, 0), exb(0, 1), shll(1), mov(1, 12), shll2(12), shll(12), ADD(1, 12), ADD(9, 12))
    W(ldbp(11, 0), exb(0, 13))
    W(ldbp(11, 0), exb(0, 0), mov(0, 2), 0xC804); a.br('bt', 'g8')
    a.ld(1, 256 * 18); W(ADD(1, 12))
    a.L('g8')
    W(0xC901, shll8(0), OR(0, 13), addi(13, 8), shlr(2), mov(2, 0), 0xC901, mov(0, 2))
    W(shll2(2), shll2(2), addi(2, 4), movi(3, BSTR), 0x0237, 0x021A)
    a.ld(3, BUF); W(ADD(3, 2), mov(13, 0), shlr2(0), shlr(0), ADD(0, 2))
    W(mov(13, 0), 0xC907, mov(0, 14), movi(3, 6))
    a.L('gp')
    W(ldbp(12, 4), exb(4, 4), ldbp(12, 5), exb(5, 5), ldbp(12, 6), exb(6, 6))
    W(mov(4, 0), shll2(0), shll2(0), mov(5, 1), shlr2(1), shlr2(1))
    a.br('bsr', 'stamp'); W(OR(1, 0))
    W(mov(5, 0), 0xC90F, shll8(0))
    a.br('bsr', 'stamp'); W(OR(6, 0))
    W(dt(3)); a.br('bf', 'gp')
    W(dt(10)); a.br('bf', 'ch')
    a.L('chd')
    # 4비트 선형(색 뱅크): 행 y(nrow*8) × 열 cx(w8) × 8 화소 = 4 B
    W(ldb0(8, 1), exb(0, 9), shll2(9), shll(9))
    a.ld(10, BUF); W(addi(10, BSTR)); a.ld(11, TEX)
    a.L('ry'); W(ldb0(8, 0), exb(0, 13), mov(10, 14))
    a.L('rx'); W(mov(14, 2))
    W(mov(2, 4), addi(4, -BSTR), mov(2, 5), addi(5, BSTR))
    W(ldb(4, 0), ldb(2, 1), OR(1, 0), ldb(5, 1), OR(1, 0), exb(0, 6), shll8(6))
    W(ldb0(4, 1), mov(0, 1), ldb0(2, 1), OR(0, 1), ldb0(5, 1), OR(1, 0), exb(0, 0), OR(0, 6), shll8(6))
    W(ldb0(4, 2), mov(0, 1), ldb0(2, 2), OR(0, 1), ldb0(5, 2), OR(1, 0), exb(0, 0), OR(0, 6))
    W(mov(6, 1), shlr8(1), mov(6, 0), shll(0), shlr8(0), OR(0, 1), mov(6, 0), shlr(0), shlr8(0), OR(0, 1))
    W(ldb0(2, 1), exb(0, 7), 0x6077, AND(0, 1), exb(1, 1))                # r7 = 글자 비트 · r1 = 테두리(팽창 − 글자)
    W(movi(3, 8), movi(6, 0))
    a.L('eb'); W(shll2(6), shll2(6), mov(7, 0), 0xC880); a.br('bt', 'e1')
    W(addi(6, 0xD)); a.br('bra', 'es'); W(0x0009)                        # 흰 글자
    a.L('e1'); W(mov(1, 0), 0xC880); a.br('bt', 'es')
    W(addi(6, 0xC))                                                      # 검정 테두리
    a.L('es'); W(shll(7), shll(1), dt(3)); a.br('bf', 'eb')
    W(0x2B62, addi(11, 4))                                               # mov.l r6,@r11
    W(addi(14, 1), dt(13)); a.br('bf', 'rx')
    W(movi(0, BSTR), ADD(0, 10), dt(9)); a.br('bf', 'ry')
    W(*[pop(r) for r in range(14, 7, -1)]); W(pop(1))
    # 명령 칸: SIZE · XA YA (지역 좌표 (176,112) 기준, 아래 가운데, 바닥 4px 여유)
    W(ldb0(1, 0), exb(0, 7), ldb0(1, 1), exb(0, 5))                   # r7 = w8 · r5 = nrow
    a.ld(2, 'cmd')
    W(mov(7, 0), shll8(0), mov(5, 6), shll2(6), shll(6), OR(6, 0), 0x8125)          # SIZE = w8<<8 | nrow*8
    W(mov(7, 0), shll2(0), 0x600B, 0x8126)                                           # XA = −w8*4
    W(mov(5, 0), shll2(0), shll(0), movi(6, 112 - 4), 0x3608, mov(6, 0), 0x8127)    # YA = 108 − nrow*8
    W(0x4F26, 0x000B, 0x0009)
    # ---- stamp ----
    a.L('stamp')
    W(shll8(0), shll2(0), shll2(0), mov(14, 1), 0x2118); a.br('bt', 'sd')
    a.L('sl'); W(shlr(0), dt(1)); a.br('bf', 'sl')
    a.L('sd'); W(mov(0, 7), shlr16(0), ldb(2, 1), OR(1, 0), stb(0, 2))
    W(mov(7, 1), shlr8(1), ldb0(2, 1), OR(1, 0), stb0(2, 1))
    W(ldb0(2, 2), OR(7, 0), stb0(2, 2), 0x000B, addi(2, BSTR))
    code = a.build(); assert CODE + len(code) <= DATA, hex(CODE + len(code))
    head = struct.pack('>IIIII', MAGIC, end_magic_addr, a.lab['sub'], a.lab['vin'], a.lab['dmae'])
    head += bytes(CODE - BLOCK - len(head))
    return head + code + bytes(DATA - CODE - len(code)) + data, a.lab


def block(sub_blob):
    """BLOCK 에 실릴 바이트 전부(머리·코드·변수·버퍼 자리·자막 자료·끝 표식) → (바이트, 라벨)"""
    end = SUBS + len(sub_blob)
    end += -end % 4
    code, lab = assemble(end)
    b = code + bytes(SUBS - BLOCK - len(code)) + sub_blob
    b += bytes(end - BLOCK - len(b)) + struct.pack('>I', MAGIC)
    assert BLOCK + len(b) <= BLOCK_END, ('BLOCK 초과', hex(BLOCK + len(b)))
    return b, lab


def patch_0bios(b0):
    """0BIOS.BIN(크기 그대로): 설치기+상주 그림 → BOOT 자리 · main 호출 리터럴 → BOOT ·
       처리기 리터럴 3개 → 상주 감싸개(RESI) · END 견본 리터럴 → TPL(RESI 안)"""
    b = bytearray(b0)
    _, rlab = image()
    bt = boot()
    o = BOOT - LOAD
    assert b[o:BOOT_END - LOAD] == bytes(BOOT_END - BOOT), '설치기 자리가 0 이 아님'
    b[o:o + len(bt)] = bt
    assert struct.unpack_from('>I', b, MAIN_LIT - LOAD)[0] == MAIN
    struct.pack_into('>I', b, MAIN_LIT - LOAD, BOOT)
    for lit, old, new in ((VBI_LIT, VBI, rlab['rvbi']), (VIN_LIT, VIN, rlab['rvin']), (DMAE_LIT, DMAE, rlab['rdmae'])):
        assert struct.unpack_from('>I', b, lit - LOAD)[0] == old, hex(lit)
        struct.pack_into('>I', b, lit - LOAD, new)
    assert struct.unpack_from('>I', b, TPL_LIT - LOAD)[0] == TPL_OLD
    struct.pack_into('>I', b, TPL_LIT - LOAD, 0x80000000 | TPL)
    assert len(b) == len(b0)
    return bytes(b), rlab


def patch_stg(stg, blk):
    assert len(stg) <= STG_PAD, ('STG 가 BLOCK 자리를 넘음', len(stg))
    return stg + bytes(STG_PAD - len(stg)) + blk
