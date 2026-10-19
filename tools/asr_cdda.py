# -*- coding: utf-8 -*-
r"""CD-DA 트랙(2~19) 받아쓰기 — 음성이 음악 트랙에 섞였는지 (2026-10-19)
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_cdda.py → work/cdda_asr.tsv
"""
import os, sys
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
from faster_whisper import WhisperModel
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = r'C:\claude\roms\ss\Radiant Silvergun (Japan)'
m = WhisperModel('large-v3', device='cuda', compute_type='float16')
out = []
for t in range(2, 20):
    p = os.path.join(DIR, 'Radiant Silvergun (Japan) (Track %02d).bin' % t)
    a = np.frombuffer(open(p, 'rb').read(), '<i2').reshape(-1, 2).astype(np.float32).mean(1) / 32768
    a16 = a[::1][np.round(np.arange(0, len(a), 44100 / 16000)).astype(int).clip(0, len(a) - 1)]
    segs, _ = m.transcribe(a16, language='ja', beam_size=5, condition_on_previous_text=False, vad_filter=False)
    for s in segs:
        out.append('%02d\t%.1f\t%.1f\t%.2f\t%s' % (t, s.start, s.end, s.no_speech_prob, s.text.strip()))
        print(out[-1], flush=True)
open(os.path.join(ROOT, 'work', 'cdda_asr.tsv'), 'w', encoding='utf-8').write('\n'.join(out))
