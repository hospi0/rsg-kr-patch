# -*- coding: utf-8 -*-
r"""CD-DA 트랙·동영상 소리에서 목소리만 분리(demucs htdemucs) → work/vocals/tNN.npy · <이름>.npy (16 kHz 모노 float32)
  음악이 큰 트랙에서 받아쓰기가 대사를 놓쳐서 (2026-10-19). 트랙 = INDEX 01 기준, 동영상 = work/<이름>.wav(16 kHz 모노)
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/sep.py 9 11 12 … OPENING ST1
"""
import os, sys, wave
import numpy as np
import torch
from demucs.pretrained import get_model
from demucs.apply import apply_model
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DIR = r'C:\claude\roms\ss\Radiant Silvergun (Japan)'
OUT = os.path.join(ROOT, 'work', 'vocals')
PREGAP = 2.0


def source(k):
    """키 → (이름, 44.1 kHz 스테레오 [2, n])"""
    if k.isdigit():
        t = int(k)
        a = np.frombuffer(open(os.path.join(DIR, 'Radiant Silvergun (Japan) (Track %02d).bin' % t), 'rb').read(),
                          '<i2').reshape(-1, 2).astype(np.float32).T / 32768
        return 't%02d' % t, a[:, int(PREGAP * 44100):]
    w = wave.open(os.path.join(ROOT, 'work', k + '.wav'))
    x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
    x = np.interp(np.arange(0, len(x), 16000 / 44100), np.arange(len(x)), x).astype(np.float32)
    return k, np.stack([x, x])


def main():
    os.makedirs(OUT, exist_ok=True)
    m = get_model('htdemucs'); m.eval()
    for k in sys.argv[1:]:
        name, a = source(k)
        with torch.no_grad():
            src = apply_model(m, torch.from_numpy(np.ascontiguousarray(a))[None], device='cpu', split=True,
                              overlap=0.25)[0]
        v = src[m.sources.index('vocals')].mean(0).numpy()
        v16 = v[np.round(np.arange(0, len(v), 44100 / 16000)).astype(int).clip(0, len(v) - 1)]
        np.save(os.path.join(OUT, name + '.npy'), v16.astype(np.float32))
        print('%s %.1fs → vocals rms %.4f / 원래 %.4f' % (name, len(v) / 44100, np.sqrt((v ** 2).mean()),
                                                       np.sqrt((a.mean(0) ** 2).mean())), flush=True)


if __name__ == '__main__':
    main()
