# -*- coding: utf-8 -*-
r"""번역 규칙 — 번역을 «읽어 들이는 순간» 막는다 (2026-10-19)
  squeeze(t)          : 표준 문장부호 목록 뒤 공백 1칸 제거(2칸 이상 = 채움, 그대로)
  validate(jp, kr)    : 막을 것 목록 — 실개행·탭, 원문 괄호 토큰(「」『』（）) 개수 다름, 빈 번역
                        (대본 줄 안 （笑）（ぁ） 같은 연기 지시는 토큰 아님 — 줄 전체 （…） 속마음만 토큰)
"""
import re

PUNCT = ',.!?:;)]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥'
_SQ = re.compile('([' + re.escape(PUNCT) + '])[ 　](?![ 　])')
TOKENS = '「」『』（）'
BANNER = ('[규칙] 부호 뒤 공백은 빌더가 뗌 · 원문 「」『』（） 개수 그대로 · `|` = 자막 쪽 나눔 · '
          '실개행 금지 · 일본어 이름은 거센소리(카·타·츠)')


def squeeze(t):
    return _SQ.sub(r'\1', t)


def validate(jp, kr):
    bad = []
    if not kr.strip():
        bad.append('빈 번역')
    if '\n' in kr or '\t' in kr:
        bad.append('실개행/탭')
    body = jp[1:-1] if jp.startswith('「') and jp.endswith('」') else jp   # 대사 바깥 「」 = 대본 표기
    if not (body.startswith('（') and body.endswith('）')):             # 줄 전체 （…） = 속마음 → 토큰
        body = re.sub(r'（[^）]*）', '', body)                            # 줄 안 （笑）（ぁ） = 연기 지시
    for c in TOKENS:
        if body.count(c) != kr.count(c):
            bad.append('토큰 %s 원문 %d / 번역 %d' % (c, body.count(c), kr.count(c)))
    return bad
