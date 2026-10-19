# -*- coding: utf-8 -*-
r"""레이디언트 실버건 배포 묶음 — dist/RadiantSilvergun_KR_<VER>/ : 트랙 01 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat
  (창궁홍련대 tools/make_dist.py 에서 2026-10-19)
  검증: 원본 트랙 01 → xdelta 적용 → md5 = 빌드 결과(work/out) md5.
  python tools/make_dist.py   (먼저 python tools/build.py --write)
"""
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
VER = 'v0.9'
XDELTA = r'C:\claude\utils\xdelta.exe'
ROMNAME = 'Radiant Silvergun (Japan)'
SRC = os.path.join(r'C:\claude\roms\ss', ROMNAME)
BUILD = os.path.join(ROOT, 'work', 'out')
NAME = 'RadiantSilvergun_KR_' + VER
TITLE = '레이디언트 실버건 (세가 새턴 일본판) 한글 패치 ' + VER
TRACKS = 19


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 1번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 01 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 01 이름으로 바꿔 넣고, 나머지 트랙과 cue 는 그대로 쓰세요
     (트랙 01 크기는 원본과 같습니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 01" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - 스테이지 대사(CD 음성) 한국어 자막 - 스테이지 3·2·4·5·6, 화면 아래에 표시
  - 동영상 자막: 오프닝 애니메이션(대사·장소/시각 안내), 엔딩 크리에이타 독백
  - 타이틀 로고 아래 읽기 줄 "레이디언트 실버건"
  - 데모(TRIAL RIDE MODE) 화면 아래 안내 문구
  - 새턴 모드·아케이드 모드 모두 적용
  - 번역 원문은 디스크에 들어 있는 공식 시나리오(FUROKU/SCENARIO.DOC)입니다


[ 알려진 점 ]

  - 원본 시나리오에 있어도 게임에 녹음이 없는 대사 몇 줄은 자막이 없습니다.
  - 화면에 원래 나오는 영어 문구(스테이지 이름·장소 안내 등)는 원본 그대로입니다.
  - 아직 끝까지 실기로 확인하지 못했습니다. 자막이 안 나오거나 어긋나는 곳이 있으면 알려 주세요.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 01 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
"%XD%" -d -f -B 268435456 -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    b = ROMNAME + ' (Track 01).bin'
    src = os.path.join(SRC, b); out = os.path.join(BUILD, b)
    patch = NAME + '.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-B', '268435456', '-s', src, out, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-B', '268435456', '-s', src, pp, chk], check=True)
    o, want, got = md5(src), md5(out), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    kbin = ROMNAME + ' (Track 01) [KR].bin'
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = (TITLE + '\n' + '=' * 60 + '\n\n' + HEAD.format(tracks=TRACKS, rom=ROMNAME, o=o, d=want)
              + BODY.format(bin=b, patch=patch))
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(
        BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    zp = shutil.make_archive(d, 'zip', os.path.dirname(d), NAME)
    notes = os.path.join(ROOT, 'dist', NAME + '_notes.md')
    open(notes, 'w', encoding='utf-8').write(
        TITLE + '\n\n- 대상: `%s` 트랙 01 (트랙 %d개)\n- 원본md5 `%s` → 패치md5 `%s`\n'
        '- 적용 방법은 zip 안 readme.txt 참고(한글패치_적용.bat 또는 xdelta).\n\n바뀌는 것\n'
        '- 스테이지 대사(CD 음성) 한국어 자막 — 스테이지 3·2·4·5·6\n'
        '- 동영상 자막: 오프닝(대사·장소/시각 안내), 엔딩 크리에이타 독백\n'
        '- 타이틀 읽기 줄 «레이디언트 실버건» · 데모 화면 안내 문구\n'
        '- 새턴 모드·아케이드 모드 모두 적용\n\n'
        '- 녹음이 없는 대사 몇 줄은 자막이 없고, 화면의 영어 문구는 원본 그대로입니다.\n'
        '- 아직 끝까지 실기로 확인하지 못했습니다.\n' % (ROMNAME, TRACKS, o, want))
    print('원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    print('zip', zp, os.path.getsize(zp), md5(zp))
    for f in sorted(os.listdir(d)):
        print('  %-50s %12d' % (f, os.path.getsize(os.path.join(d, f))))


if __name__ == '__main__':
    main()
