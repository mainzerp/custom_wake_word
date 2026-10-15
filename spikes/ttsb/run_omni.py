"""Spike B: OmniVoice (voice clone; --design uses instruct-based voice design).

  docker exec -e PYTHONPATH=/app -e HF_HOME=/app/data/cache/huggingface cww-trainer \
    /opt/spike/omni/bin/python spikes/ttsb/run_omni.py
"""

import argparse
import random

import torch
from omnivoice import OmniVoice

from spikes.ttsb.common import DESIGNS, TEXTS, THROUGHPUT_N, Timer, out_dir, refs, save, write_result

DESIGN_ATTRS = ["female, young adult", "male, elderly, low pitch", "male, teenager", "female, middle-aged, low pitch",
                "male, middle-aged", "female, child, high pitch"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", action="store_true")
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    name = "omnivoice-design" if args.design else "omnivoice"

    with Timer() as t_load:
        model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16)
    sr = model.sampling_rate
    d = out_dir(name)
    clips = []

    if args.design:
        voices = [(f"d{i}", a) for i, a in enumerate(DESIGN_ATTRS[: len(DESIGNS)])]
    else:
        voices = [(r["id"], model.create_voice_clone_prompt(ref_audio=r["path"], ref_text=r["text"])) for r in refs()]

    def run(texts, vs):
        if args.design:
            return model.generate(text=texts, language="German", instruct=vs)
        return model.generate(text=texts, language="German", voice_clone_prompt=vs)

    for key, text in TEXTS.items():
        with Timer() as t:
            wavs = run([text] * len(voices), [v for _, v in voices])
        for (vid, _), w in zip(voices, wavs):
            clips.append({"file": f"{vid}_{key}.wav", "voice": vid, "text": text,
                          "seconds": save(d, f"{vid}_{key}", w, sr), "batch_s": round(t.s, 2)})

    rng = random.Random(0)
    pool = [v for _, v in voices]
    torch.cuda.synchronize()
    with Timer() as t_tp:
        n = 0
        while n < THROUGHPUT_N:
            batch = [rng.choice(pool) for _ in range(args.batch)]
            run([TEXTS["jarvis"]] * len(batch), batch)
            n += len(batch)
    write_result(name, {
        "model": "k2-fsa/OmniVoice", "load_s": round(t_load.s, 1), "sample_rate": sr, "clips": clips,
        "throughput": {"n": n, "batch": args.batch, "seconds": round(t_tp.s, 1), "clips_per_s": round(n / t_tp.s, 2)},
        "vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1),
    })


if __name__ == "__main__":
    main()
