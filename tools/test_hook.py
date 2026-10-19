# -*- coding: utf-8 -*-
"""자막 훅 검산(2026-10-19, 건담 외전 test_hook 에서): CD 레지스터 흉내(PLAY·FAD) → 상주 감싸개 → 본체
   쪽 고르기 · 4비트 그림(glyphpack.reference 와 같은지) · 명령 칸 · END 점프 · 우선순위 · 꺼짐 · 본체 없을 때 아무것도 안 함"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import glyphpack as G
import hook as H, subs, sh2sim as S

B0 = open(os.path.join(ROOT, 'work', 'disc', '0BIOS.BIN'), 'rb').read()


def mem(with_block=True):
    m = S.Mem(); m.add(0x06000000, 0x100000); m.add(0x05C00000, 0x80000); m.add(0x05F00000, 0x1000)
    m.add(0x05F80000, 0x200); m.add(0x05890000, 0x100)
    b0, rlab = H.patch_0bios(B0)
    m._f(H.LOAD)[0][H.LOAD - 0x06000000:H.LOAD - 0x06000000 + len(b0)] = b0
    assert m.r32(H.MAIN_LIT) == H.BOOT
    S.run(m, H.BOOT, stop=H.MAIN)                                      # 부팅 설치기 → 상주 자리 채우고 main 으로
    img, _ = H.image()
    assert bytes(m.r8(H.RESI + i) for i in range(len(img))) == img, '설치기 복사 다름'
    sb, _ = subs.blob(H.SUBS)
    blk, lab = H.block(sb)
    if with_block:
        m._f(H.BLOCK)[0][H.BLOCK - 0x06000000:H.BLOCK - 0x06000000 + len(blk)] = blk
    m.w16(H.SHADOW + 0xF2, 0x0505); m.w16(H.SHADOW + 0xF6, 0x0605)
    return m, rlab, lab


def cd(m, status, fad):
    m.w16(H.CR1, status << 8); m.w16(H.CR1 + 8, (fad >> 16) & 0xFF); m.w16(H.CR1 + 12, fad & 0xFFFF)


def ref_tex(lines):
    w8, nrow, chars = G.layout(lines); px = G.reference(w8, nrow, chars).ravel()
    nib = [{0: 0, 1: 0xC, 15: 0xD}[int(v)] for v in px]
    return w8, nrow, bytes((nib[i] << 4) | nib[i + 1] for i in range(0, len(nib), 2))


def frame(m, rlab):
    S.run(m, rlab['rvbi'], calls={H.VBI: lambda r, mm: None})


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    F = subs.track_fads(); C = subs.cues(); ok = True
    for t in (2, 10, 16, 18):
        pages = subs.pages_for(C[t])
        for pi in (0, len(pages) - 1):
            t0, t1, lines = pages[pi]; fad = F[t][0] + int(round(t0 * 75)) + 2
            for listlen in (0, 3):
                m, rlab, lab = mem()
                for q in range(listlen): m.w16(H.LIST + 32 * q, 0x0000); m.w16(H.LIST + 32 * q + 8, 0x1234)
                m.w16(H.LIST + 32 * listlen, 0x8000); m.w16(H.LIST + 32 * listlen + 32, 0x4321)
                cd(m, 0x23, fad); frame(m, rlab)
                X = H.LIST + 32 * listlen; O = H.OWN
                w8, nrow, tex = ref_tex(lines)
                cmd = [m.r16(O + 2 * i) for i in range(8)]
                want = [0, 0, 0x0080, H.COLR, H.TEXA, w8 << 8 | nrow * 8, (-w8 * 4) & 0xFFFF, (108 - nrow * 8) & 0xFFFF]
                got = bytes(m.r8(H.TEX + i) for i in range(len(tex)))
                c0 = m.r16(H.CRAM_BK) == 0 and m.r16(H.CRAM_BK + 2) == 0x7FFF and m.r16(H.PRISB) == 0x0705 and m.r16(H.PRISD) == 0x0607 \
                    and m.r16(H.SHADOW + 0xF2) == 0x0505                       # 사본은 안 건드림
                c = (cmd == want and c0, m.r16(X) == 0x5000 and m.r16(X + 2) == H.OWNL, m.r16(O + 32) == 0x8000,
                     m.r16(X + 32) == 0x4321, got == tex)
                cd(m, 0x21, fad)                                               # PAUSE
                frame(m, rlab); keep = m.r16(X) == 0x5000                     # 한 프레임 «없음»은 유지
                for _ in range(H.OFFN): frame(m, rlab)
                c += (keep and m.r16(X) == 0x8000,)
                print('트랙%02d 쪽%d 게임명령%d: 명령 %s · 점프 %s · 우리END %s · 다음칸 그대로 %s · 그림 %s · 끝나면 END %s  %s' % ((t, pi, listlen) + c + (lines,)))
                if not c[0]: print('   ', [hex(x) for x in cmd], [hex(x) for x in want], hex(m.r16(H.PRISB)), hex(m.r16(H.PRISD)))
                ok &= all(c)
    # 링크로 이어진 명령표: 0번 → 5번(점프 지정), 1번 = 가짜 END → 진짜 END(5번)에만 점프 / DMA 끝·VBlank-IN 감싸개
    pages = subs.pages_for(C[2]); fad = F[2][0] + int(round(pages[0][0] * 75)) + 2
    m, rlab, lab = mem(); m.w16(H.LIST, 0x1000); m.w16(H.LIST + 2, 5 * 32 // 8); m.w16(H.LIST + 32, 0x8000); m.w16(H.LIST + 5 * 32, 0x8000)
    cd(m, 0x23, fad); frame(m, rlab)
    hit = m.r16(H.LIST + 5 * 32) == 0x5000 and m.r16(H.LIST + 32) == 0x8000
    m.w16(H.LIST + 5 * 32, 0x8000); S.run(m, rlab['rdmae'], calls={H.DMAE: lambda r, mm: None})
    hit2 = m.r16(H.LIST + 5 * 32) == 0x5000
    print('링크 따라 진짜 END 에 점프 %s · DMA 끝에 다시 넣기 %s' % (hit, hit2)); ok &= hit and hit2
    m.w16(H.PRISB, 0x0505); m.w16(H.PRISD, 0x0605); S.run(m, rlab['rvin'], calls={H.VIN: lambda r, mm: None})
    hit3 = m.r16(H.PRISB) == 0x0705 and m.r16(H.PRISD) == 0x0607; print('VBlank-IN 뒤 S3·S6 = 7 다시 %s' % hit3); ok &= hit3
    hit4 = m.r16(H.TPL) == 0x5000 and m.r16(H.TPL + 2) == H.OWNL
    cd(m, 0x23, F[3][0] - 1)                                                   # 트랙 사이(어느 트랙도 아님)
    for _ in range(H.OFFN + 1): frame(m, rlab)
    hit4 &= m.r16(H.TPL) == 0x8000; print('견본: 켜지면 점프·꺼지면 END %s' % hit4); ok &= hit4
    # 트랙 19(음악만)·데이터 트랙 FAD = 자막 없음
    for fad in (F[19][0] + 300, 5000):
        m, rlab, lab = mem(); m.w16(H.LIST, 0x8000); cd(m, 0x23, fad); frame(m, rlab)
        hit = m.r16(H.LIST) == 0x8000; print('자막 없는 FAD %d → 그대로 %s' % (fad, hit)); ok &= hit
    # 본체(BLOCK) 없음 = 감싸개가 원래 처리기만 부름
    m, rlab, lab = mem(with_block=False); m.w16(H.LIST, 0x8000); cd(m, 0x23, F[2][0] + 200)
    called = []
    S.run(m, rlab['rvbi'], calls={H.VBI: lambda r, mm: called.append(1)})
    hit = m.r16(H.LIST) == 0x8000 and called == [1]; print('본체 없음 → 원래 처리기만 %s' % hit); ok &= hit
    res, _ = H.resident(); sb, _ = subs.blob(H.SUBS); blk, _ = H.block(sb); bt = H.boot()
    print('상주 %d B(자리 %d, TPL %s) · 설치기+그림 %d B(자리 %d) · 본체 %d B → 끝 %s(한계 %s)' % (
        len(res), H.TPL - H.RESI, hex(H.TPL), len(bt), H.BOOT_END - H.BOOT, len(blk), hex(H.BLOCK + len(blk)), hex(H.BLOCK_END)))
    print('결과', '통과' if ok else '실패')


if __name__ == '__main__':
    main()
