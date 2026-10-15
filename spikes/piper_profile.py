"""Profile Spike A: where does the time go (inference vs. resample vs. disk)?"""

import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
from piper import PiperVoice
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).parent))
from piper_throughput import batched_session  # noqa: E402

model = Path("data/models/piper/de_DE-mls-medium.onnx")
voice = PiperVoice.load(model)
ids = [i for s in voice.phonemize("Dscharwis") for i in voice.phonemes_to_ids(s)]
rng = np.random.default_rng(0)

for label, opts in [
    ("cuda heuristic", {"cudnn_conv_algo_search": "HEURISTIC"}),
    ("cuda default", {}),
]:
    sess = ort.InferenceSession(
        str(model.with_suffix(".batch.onnx")), providers=[("CUDAExecutionProvider", opts)]
    )
    assert "CUDAExecutionProvider" in sess.get_providers()
    for batch in (32, 128):
        def run(scales):
            return sess.run(None, {
                "input": np.tile(np.array(ids, dtype=np.int64), (batch, 1)),
                "input_lengths": np.full(batch, len(ids), dtype=np.int64),
                "scales": np.array(scales, dtype=np.float32),
                "sid": rng.integers(0, 236, batch).astype(np.int64),
            })
        run([0.5, 0.8, 0.3])
        t = time.perf_counter()
        n = 0
        for _ in range(8):
            audio, _ = run([rng.uniform(0.3, 0.8), rng.uniform(0.55, 1.0), rng.uniform(0.2, 0.5)])
            n += batch
        dt = time.perf_counter() - t
        print(f"{label:15s} batch={batch:3d}: inference {n / dt:7.1f} samples/s, out shape {audio.shape}")

rows = audio.reshape(audio.shape[0], -1)
t = time.perf_counter()
clips = [resample_poly(r, 16000, 22050).astype(np.float32) for r in rows]
print(f"resample: {len(rows) / (time.perf_counter() - t):.0f} clips/s")

for target in (Path("data/spikes/profile_io"), Path(tempfile.mkdtemp())):
    target.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    for i, c in enumerate(clips):
        sf.write(target / f"{i}.wav", c[:20000], 16000, subtype="PCM_16")
    print(f"write {target}: {len(clips) / (time.perf_counter() - t):.0f} files/s")
