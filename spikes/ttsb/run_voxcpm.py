"""Spike B: VoxCPM2 (reference cloning without transcript, plus voice design from a description).

  docker exec -e PYTHONPATH=/app -e HF_HOME=/app/data/cache/huggingface cww-trainer \
    /opt/spike/voxcpm/bin/python spikes/ttsb/run_voxcpm.py
"""

import random

import torch
from voxcpm import VoxCPM

from spikes.ttsb.common import DESIGNS, TEXTS, THROUGHPUT_N, Timer, out_dir, refs, save, write_result


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    with Timer() as t_load:
        model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, device="cuda")
    sr = model.tts_model.sample_rate
    gen = {"cfg_value": 2.0, "inference_timesteps": 10, "max_len": 400}

    voices = [(r["id"], {"reference_wav_path": r["path"]}, "") for r in refs()]
    voices += [(f"d{i}", {}, f"({desc})") for i, desc in enumerate(DESIGNS)]
    d = out_dir("voxcpm2")
    clips = []
    for key, text in TEXTS.items():
        for vid, kw, prefix in voices:
            with Timer() as t:
                wav = model.generate(text=prefix + text, **kw, **gen)
            clips.append({"file": f"{vid}_{key}.wav", "voice": vid, "text": text,
                          "seconds": save(d, f"{vid}_{key}", wav, sr), "batch_s": round(t.s, 2)})

    rng = random.Random(0)
    torch.cuda.synchronize()
    with Timer() as t_tp:
        for _ in range(THROUGHPUT_N // 4):
            _, kw, prefix = rng.choice(voices)
            model.generate(text=prefix + TEXTS["jarvis"], **kw, **gen)
    n = THROUGHPUT_N // 4
    write_result("voxcpm2", {
        "model": "openbmb/VoxCPM2", "load_s": round(t_load.s, 1), "sample_rate": sr, "clips": clips,
        "throughput": {"n": n, "batch": 1, "seconds": round(t_tp.s, 1), "clips_per_s": round(n / t_tp.s, 2)},
        "vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1),
    })


if __name__ == "__main__":
    main()
