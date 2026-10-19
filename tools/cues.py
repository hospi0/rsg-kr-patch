# -*- coding: utf-8 -*-
r"""자막 쪽 목록 — 줄 시각(work/timing.tsv + 손 고침 work/timing_fix.tsv) + 번역(work/text/ko.tsv) → work/text/cues.tsv
  열: track cda id page start end kr   (시각 = 트랙 INDEX 01 기준 초 / 동영상은 영상 처음부터)
  · 쪽 시각이 따로 있으면(timing page ≥1, jp_pages.tsv 로 맞춘 것·손 고침) 그대로 쓴다.
  · 없으면 한 줄 안 `|` 쪽을 번역 글자 수 비율로 나누고, 받아쓰기 구간 경계(±1.5초) 가까이 있으면 거기로 붙인다.
  · 끝 = 말 끝 + 0.6초(다음 쪽 시작 전까지), 쪽 최소 1.0초.
  · 시각 없는 줄(음성 없음)은 «빠진 줄»로 보고만.
  python tools/cues.py
"""
import csv, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rules

TAIL, MIN = 0.6, 1.0


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def main():
    print(rules.BANNER)
    jp = {r['id']: r['jp'] for r in read('work/text/lines.tsv')}
    ko = {}
    bad = 0
    for r in read('work/text/ko.tsv'):
        e = rules.validate(jp[r['id']], r['kr'])
        if e:
            print('  ⛔', r['id'], e); bad += 1
        ko[r['id']] = rules.squeeze(r['kr'])
    assert not bad, '번역 규칙 위반 %d줄' % bad
    fix = {(r['id'], int(r['page'])): (float(r['start']), float(r['end'])) for r in read('work/timing_fix.tsv')}
    T = read('work/timing.tsv')
    bounds = {}; spans = {}; meta = {}
    for r in T:
        if r['id'] == '#asr':
            b = []
            for a, z in re.findall(r'\[([\d.]+)-([\d.]+)\]', r['jp']):
                b += [float(a), float(z)]
            bounds[r['track']] = b; continue
        pg = int(r['page'])
        spans.setdefault(r['id'], {})[pg] = fix.get((r['id'], pg), (float(r['start']), float(r['end'])))
        meta[r['id']] = (r['track'], r['cda'])
    for (i, pg), v in fix.items():                     # 손 고침에만 있는 쪽(OP03_17 쪽 나눔 등)
        spans.setdefault(i, {})[pg] = v
    order = list(dict.fromkeys(r['track'] for r in T))
    raw = []
    for i, sp in spans.items():
        tr, cda = meta[i]
        pages = ko[i].split('|')
        if any(p >= 1 for p in sp):                    # 쪽 시각 따로
            sp = {p: v for p, v in sp.items() if p >= 1}
            assert sorted(sp) == list(range(1, len(pages) + 1)), (i, sorted(sp), len(pages))
            if any(v[0] < 0 for v in sp.values()):
                print('  ⚠️쪽 시각 빠짐', tr, i, sp)
            for p in sorted(sp):
                raw.append([tr, cda, i, p, sp[p][0], sp[p][1], pages[p - 1]])
            continue
        st, en = sp[0]
        if st < 0:
            print('  빠진 줄(음성 없음)', tr, i, jp[i]); continue
        w = [max(len(p), 1) for p in pages]; acc = 0; cut = [st]
        for k in range(len(pages) - 1):
            acc += w[k]; x = st + (en - st) * acc / sum(w)
            near = [b for b in bounds.get(tr, []) if st < b < en and abs(b - x) <= 1.5]
            cut.append(min(near, key=lambda b: abs(b - x)) if near else x)
        cut.append(en)
        for k, p in enumerate(pages):
            raw.append([tr, cda, i, k + 1, cut[k], cut[k + 1], p])
    raw.sort(key=lambda x: (order.index(x[0]), x[4]))
    out = []
    for n, c in enumerate(raw):
        nxt = raw[n + 1][4] if n + 1 < len(raw) and raw[n + 1][0] == c[0] else 1e9
        if c[4] > nxt or (n and raw[n - 1][0] == c[0] and raw[n - 1][5] > c[4] + 0.3):
            print('  ⚠️겹침', c[0], c[2], c[3], '%.2f' % c[4])
        end = min(max(c[5] + TAIL, c[4] + MIN), max(nxt - 0.05, c[5]))
        out.append(c[:5] + [end, c[6]])
    with open(os.path.join(ROOT, 'work', 'text', 'cues.tsv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(['track', 'cda', 'id', 'page', 'start', 'end', 'kr'])
        for c in out:
            w.writerow(c[:4] + ['%.2f' % c[4], '%.2f' % c[5], c[6]])
    print('쪽 %d개 → work/text/cues.tsv' % len(out))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
