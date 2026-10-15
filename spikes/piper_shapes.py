"""Piper on CUDA: per-batch latency with varying output shapes under different CUDA EP options.

  docker exec -e PYTHONPATH=/app cww-trainer py-tts spikes/piper_shapes.py

Result (RTX 3090, 3840 clips "Dscharwis", random scales):
  heuristic b128               first third  285/s  rest    4/s  max 261.67s  total 6/s
  heuristic b64                first third  143/s  rest  285/s  max 2.36s  total 214/s
  heuristic b32                first third  184/s  rest  210/s  max 0.29s  total 201/s
  heuristic+same-as-req b64    first third  279/s  rest  303/s  max 0.36s  total 294/s
  heuristic+no-max-ws b64      first third  286/s  rest  307/s  max 0.47s  total 300/s
"""

import gc
import sys
import time

import numpy as np
import onnxruntime as ort

from trainer.tts.generate import Synth

H = {"cudnn_conv_algo_search": "HEURISTIC"}
CASES = [
    ("heuristic b128", H, 128),
    ("heuristic b64", H, 64),
    ("heuristic b32", H, 32),
    ("heuristic+same-as-req b64", {**H, "arena_extend_strategy": "kSameAsRequested"}, 64),
    ("heuristic+no-max-ws b64", {**H, "cudnn_conv_use_max_workspace": "0"}, 64),
]
CLIPS = 3840

synth = Synth("de")
ids = synth.ids("Dscharwis")
model = str(synth.session._model_path)
only = sys.argv[1:]
for label, opts, batch in CASES:
    if only and not any(o in label for o in only):
        continue
    synth.session = None
    gc.collect()
    synth.session = ort.InferenceSession(model, providers=[("CUDAExecutionProvider", opts)])
    rng = np.random.default_rng(0)
    times = []
    for _ in range(CLIPS // batch):
        scales = [rng.uniform(0.3, 0.8), rng.uniform(0.55, 1.0), rng.uniform(0.2, 0.5)]
        t = time.perf_counter()
        synth.infer(ids, rng.integers(0, 236, batch), scales)
        times.append(time.perf_counter() - t)
    t = np.array(times)
    k = len(t) // 3
    print(f"{label:28s} first third {k * batch / t[:k].sum():4.0f}/s  rest {(len(t) - k) * batch / t[k:].sum():4.0f}/s  "
          f"max {t.max():.2f}s  total {CLIPS / t.sum():.0f}/s", flush=True)
