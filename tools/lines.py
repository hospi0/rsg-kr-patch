# -*- coding: utf-8 -*-
r"""대본(work/scenario.txt) → 대사 작업표 work/text/lines.tsv
  열: id  장면  화자  원문  메모(말투 지시 등)
  장면 = OP00‥OP03(오프닝 애니) · S3 S2 S4 S5 S6 S1(게임 순서) · ED(엔딩 애니)
  python tools/lines.py
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'scenario.txt')
OUT = os.path.join(ROOT, 'work', 'text', 'lines.tsv')

Z2H = str.maketrans('０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ',
                    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def section(line):
    m = re.match(r'ＯＰＥＮＩＮＧ ＤＥＭＯ\s+ＳＣＥＮＥ：(..)', line)
    if m:
        return 'OP' + m.group(1).translate(Z2H)
    m = re.match(r'(?:（)?ＳＴＡＧＥ－(.)(?:）)?\s+(ＥＮＤＩＮＧ)?', line)
    if m and line.strip().endswith(('ＲＥＴＵＲＮ', 'ＲＥＭＩＮＩＳＣＥＮＣＥ', 'ＥＶＡＳＩＯＮ', 'ＶＩＣＴＩＭ',
                                     'ＯＲＩＧＩＮ', 'ＬＩＮＫ', 'ＥＮＤＩＮＧ')):
        return 'ED' if m.group(2) else 'S' + m.group(1).translate(Z2H)
    return None


def split_note(block):
    """「…」 바깥 꼬리(（淡々と） 등)는 메모로. 생각(（…）)·「 없는 덩어리는 통째로."""
    if '「' in block:
        a = block.index('「'); d = 0
        for b in range(a, len(block)):
            d += {'「': 1, '」': -1}.get(block[b], 0)
            if d == 0:
                return block[a:b + 1], (block[:a] + block[b + 1:]).strip()
    return block, ''


def opened(blk):
    """「 가 아직 안 닫혔으면 빈 줄도 대사 안(엔딩 독백)."""
    t = '\n'.join(blk)
    return t.count('「') > t.count('」')


def norm(t):
    t = re.sub(r'\n\s*', '', t)                 # 대본 줄바꿈·들여쓰기 = 조판일 뿐
    t = re.sub(r'(?<=・) (?=・)', '', t)          # 「・ ・ ・」 → 「・・・」
    return t.strip()


def main():
    L = open(SRC, encoding='utf-8').read().split('\n')
    rows = []; sec = 'OP00'; i = 0; n = {}
    while i < len(L):
        s = section(L[i])
        if s:
            sec = s; i += 1; continue
        m = re.match(r'^(\S.*?)：\s*$', L[i])
        t = L[i]
        if m or t.startswith('：「'):
            who = m.group(1) if m else '石の様な物体'
            j = i + 1 if m else i
            blk = []
            while j < len(L) and (L[j].strip() or opened(blk)):
                blk.append(L[j][1:] if L[j].startswith('：') else L[j]); j += 1
            if blk:
                jp, note = split_note('\n'.join(blk))
                # 영어 자막 테롭은 괄호 안 일본어 뜻을 메모로
                n[sec] = n.get(sec, 0) + 1
                rows.append(('%s_%02d' % (sec, n[sec]), sec, who, norm(jp), norm(note)))
            i = j; continue
        if sec in ('OP00', 'S1') and t.startswith('「Ｎｏｗ'):
            blk = []
            j = i
            while j < len(L) and L[j].strip():
                blk.append(L[j]); j += 1
            jp, note = split_note('\n'.join(blk))
            n[sec] = n.get(sec, 0) + 1
            rows.append(('%s_%02d' % (sec, n[sec]), sec, 'テロップ', norm(jp), norm(note)))
            i = j; continue
        i += 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('id\tsec\twho\tjp\tnote\n')
        for r in rows:
            assert all('\t' not in c and '\n' not in c for c in r), r
            f.write('\t'.join(r) + '\n')
    print(len(rows), '줄 →', OUT)
    for k, v in n.items():
        print(' ', k, v)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
