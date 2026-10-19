# -*- coding: utf-8 -*-
r"""대사 소리(CD-DA 트랙·동영상) ↔ 대본 줄 시각 맞추기 (2026-10-19)
  소리마다 «들어 있을 대본 줄»을 위스퍼 힌트로 주고 낱말 시각을 받은 뒤,
  양쪽을 히라가나 읽기(pykakasi)로 바꿔 글자 단위로 맞춘다 → 줄(쪽)마다 시작·끝·일치율.
  · 트랙 시각 = INDEX 01 기준(트랙 bin 앞 2초 pregap 뺌). 동영상 시각 = 영상 처음부터(work/<이름>.wav).
  · 긴 줄은 work/text/jp_pages.tsv 에 원문을 번역과 같은 `|` 쪽으로 나눠 두면 쪽마다 따로 맞춘다.
  · 음악이 큰 소리는 먼저 tools/sep.py 로 목소리 분리(work/vocals/<키>.npy 가 있으면 그걸 쓰고, 소리 구간마다 따로 받아씀).
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/align.py [키…]   (키 = 트랙 번호 2‥19 · OPENING · ST1)
  → work/timing.tsv (열: track cda id page start end cover jp — page 0 = 줄 통째)
"""
import csv, difflib, os, re, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DIR = r'C:\claude\roms\ss\Radiant Silvergun (Japan)'
PREGAP = 2.0
OUT = os.path.join(ROOT, 'work', 'timing.tsv')


def rng(sec, a, b):
    return ['%s_%02d' % (sec, i) for i in range(a, b + 1)]


# 키 → (디스크 이름, 대본 줄). 트랙 = 디스크 /STxx.CDA(LBA 순). 음성 없는 줄(S4_01·S5_20 테롭·S1 전부)은 뺌.
MAP = {
    '2': ('ST31', rng('S3', 1, 6)), '3': ('ST32', rng('S3', 7, 7)), '4': ('ST33', rng('S3', 8, 12)),
    '5': ('ST34', rng('S3', 13, 15)),
    '6': ('ST21', rng('S2', 1, 5)), '7': ('ST22', rng('S2', 6, 6)), '8': ('ST23', rng('S2', 7, 9)),
    '9': ('ST24', rng('S2', 10, 17)), '10': ('ST25', rng('S2', 18, 29)),
    '11': ('ST41', rng('S4', 2, 9)), '12': ('ST42', rng('S4', 10, 14)), '13': ('ST43', rng('S4', 15, 16)),
    '14': ('ST44', rng('S4', 17, 21)),
    '15': ('ST51', rng('S5', 1, 4)), '16': ('ST52', rng('S5', 5, 19)),
    '17': ('ST61', rng('S6', 1, 6)), '18': ('ST62', rng('S6', 7, 10)),
    '19': ('ST1', []),
    'OPENING': ('OPENING.CPK', rng('OP01', 1, 15) + rng('OP02', 1, 9) + rng('OP03', 1, 17)),
    'ST1': ('ST1.CPK', ['ED_01']),
}

import pykakasi
KK = pykakasi.kakasi()
DROP = re.compile(r'[\s「」『』（）()・…‥、。，．！？!?～〜ー―\-:：]')


def clean(jp):
    if not (jp.startswith('（') and jp.endswith('）')):   # 줄 전체가 （…） = 속마음 대사(S5_04) — 그대로
        jp = re.sub(r'（[^）]*）', '', jp)        # （ぁ）（笑）（間違いでは） = 대본 지시·안 들리는 소리
    return jp.replace('「', '').replace('」', '').strip()


def reading(t):
    return DROP.sub('', ''.join(x['hira'] for x in KK.convert(t)))


def table(p):
    out = {}
    if os.path.exists(os.path.join(ROOT, p)):
        with open(os.path.join(ROOT, p), encoding='utf-8') as f:
            for r in csv.DictReader(f, delimiter='\t'):
                out[r['id']] = r
    return out


def keyname(k):
    return 'track %02d' % int(k) if k.isdigit() else k


def vocals_path(k):
    return os.path.join(ROOT, 'work', 'vocals', ('t%02d' % int(k) if k.isdigit() else k) + '.npy')


def load(k):
    v = vocals_path(k)
    if os.path.exists(v):
        return np.load(v)
    if not k.isdigit():                                             # 동영상 소리 = 16 kHz 모노 wav
        import wave
        w = wave.open(os.path.join(ROOT, 'work', k + '.wav'))
        return np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
    a = np.frombuffer(open(os.path.join(DIR, 'Radiant Silvergun (Japan) (Track %02d).bin' % int(k)), 'rb').read(),
                      '<i2').reshape(-1, 2).astype(np.float32).mean(1) / 32768
    a = a[int(PREGAP * 44100):]
    return a[np.round(np.arange(0, len(a), 44100 / 16000)).astype(int).clip(0, len(a) - 1)]


def regions(a, db_on=50, gap=0.4, pad=0.25):
    """0.1초 창 크기 곡선에서 말소리 구간 → [(시작초, 조각)]. 틈 gap 초 미만은 이어 붙인다."""
    w = 1600; n = len(a) // w
    db = 20 * np.log10(np.sqrt((a[:n * w].reshape(n, w) ** 2).mean(1)) * 32768 + 1)
    on = np.flatnonzero(db >= db_on)
    if not len(on):
        return []
    out = []; s = e = on[0]
    for i in on[1:]:
        if (i - e) * .1 > gap:
            out.append((s, e)); s = i
        e = i
    out.append((s, e))
    res = []
    for s, e in out:
        a0 = max(0.0, s * .1 - pad); a1 = min(len(a) / 16000, (e + 1) * .1 + pad)
        res.append((a0, a[int(a0 * 16000):int(a1 * 16000)]))
    return res


def main():
    from faster_whisper import WhisperModel
    L = table('work/text/lines.tsv'); P = table('work/text/jp_pages.tsv')
    keys = sys.argv[1:] or list(MAP)
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    old = []
    if os.path.exists(OUT) and sys.argv[1:]:
        with open(OUT, encoding='utf-8') as f:
            old = [r for r in csv.reader(f, delimiter='\t') if r[0] != 'track' and r[0] not in keys]
    rows = []
    for k in keys:
        cda, ids = MAP[k]
        units = []                                   # (id, 쪽, 원문)
        for i in ids:
            if i in P:
                units += [(i, n + 1, j) for n, j in enumerate(P[i]['jp'].split('|'))]
            else:
                units.append((i, 0, clean(L[i]['jp'])))
        prompt = '。'.join(u[2] for u in units)
        audio = load(k)
        chars = []                                   # (글자, 시각)
        asr = []
        # 분리 목소리는 소리 구간마다 따로 받아쓴다 — 통째로 주면 30초 창 뒤를 «말 없음»으로 버린다
        for off, piece in (regions(audio) if os.path.exists(vocals_path(k)) else [(0.0, audio)]):
            segs, _ = m.transcribe(piece, language='ja', beam_size=5, word_timestamps=True,
                                   condition_on_previous_text=False, vad_filter=False,
                                   initial_prompt=prompt[-600:] or None)
            for s in segs:
                asr.append('[%.1f-%.1f] %s' % (off + s.start, off + s.end, s.text.strip()))
                for w in s.words or []:
                    rd = reading(w.word)
                    for c_i, c in enumerate(rd):
                        chars.append((c, off + w.start + (w.end - w.start) * (c_i + .5) / len(rd)))
        print('== %s %s (%s)' % (keyname(k), cda, ', '.join(ids) or '대본 줄 없음'))
        for x in asr:
            print('   ', x)
        A = ''.join(c for c, _ in chars)
        S = ''; own = []
        for u in range(len(units)):
            r = reading(units[u][2]); S += r; own += [u] * len(r)
        sm = difflib.SequenceMatcher(None, S, A, autojunk=False)
        hit = [[] for _ in units]
        for blk in sm.get_matching_blocks():
            for q in range(blk.size):
                hit[own[blk.a + q]].append(chars[blk.b + q][1])
        for u, (i, pg, jp) in enumerate(units):
            n = own.count(u); h = hit[u]
            st, en = (min(h), max(h)) if h else (-1, -1)
            rows.append([k, cda, i, str(pg), '%.2f' % st, '%.2f' % en, '%.2f' % (len(h) / max(n, 1)), jp])
            print('   %-6s %2s %6.2f %6.2f  %3d%%  %s' % (i, pg or '', st, en, 100 * len(h) // max(n, 1), jp))
        rows.append([k, cda, '#asr', '', '', '', '', ' | '.join(asr)])
    order = list(MAP)
    rows = sorted(old + rows, key=lambda r: order.index(r[0]))
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(['track', 'cda', 'id', 'page', 'start', 'end', 'cover', 'jp'])
        w.writerows(rows)
    print('→', OUT)


if __name__ == '__main__':
    main()
