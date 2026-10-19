# -*- coding: utf-8 -*-
r"""work/tne/*.wav 받아쓰기(위스퍼 large-v3, VAD 끔) → work/tne_asr.tsv (2026-10-19)
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_tne.py
"""
import glob, os, sys, wave
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
from faster_whisper import WhisperModel
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = WhisperModel('large-v3', device='cuda', compute_type='float16')
out = []
for p in sorted(glob.glob(os.path.join(ROOT, 'work', 'tne', '*.wav'))):
    w = wave.open(p); sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
    a16 = np.interp(np.arange(0, len(a), sr / 16000), np.arange(len(a)), a).astype(np.float32)
    segs, info = m.transcribe(a16, language='ja', beam_size=5, condition_on_previous_text=False, vad_filter=False)
    segs = list(segs); t = ''.join(s.text for s in segs).strip()
    nsp = min([s.no_speech_prob for s in segs] or [1])
    out.append('%s\t%.2f\t%.2f\t%s' % (os.path.basename(p), len(a) / sr, nsp, t))
    print(out[-1], flush=True)
open(os.path.join(ROOT, 'work', 'tne_asr.tsv'), 'w', encoding='utf-8').write('\n'.join(out))
