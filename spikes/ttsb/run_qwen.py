"""Spike B: Qwen3-TTS (clone with 0.6B/1.7B Base, voice design with 1.7B VoiceDesign).

  docker exec -e PYTHONPATH=/app -e HF_HOME=/app/data/cache/huggingface cww-trainer \
    /opt/spike/qwen/bin/python spikes/ttsb/run_qwen.py --variant 06b
"""

import argparse
import random

import torch
from qwen_tts import Qwen3TTSModel

from spikes.ttsb.common import DESIGNS, TEXTS, THROUGHPUT_N, Timer, out_dir, refs, save, write_result

VARIANTS = {
    "06b": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "17b": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "17b-design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
}
GEN = {"max_new_tokens": 120, "do_sample": True}  # 12 Hz codec: 120 tokens = 10 s, caps decode runaways


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=VARIANTS, required=True)
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    name = f"qwen-{args.variant}"
    design = args.variant.endswith("design")

    with Timer() as t_load:
        model = Qwen3TTSModel.from_pretrained(VARIANTS[args.variant], device_map="cuda:0", dtype=torch.bfloat16,
                                              attn_implementation="sdpa")
    d = out_dir(name)
    clips = []

    def run(texts, voices):
        if design:
            return model.generate_voice_design(text=texts, instruct=voices, language=["German"] * len(texts), **GEN)
        return model.generate_voice_clone(text=texts, language=["German"] * len(texts), voice_clone_prompt=voices, **GEN)

    if design:
        voices = [(f"d{i}", v) for i, v in enumerate(DESIGNS)]
    else:
        rs = refs()
        prompts = model.create_voice_clone_prompt(ref_audio=[r["path"] for r in rs], ref_text=[r["text"] for r in rs])
        voices = [(r["id"], p) for r, p in zip(rs, prompts)]

    for key, text in TEXTS.items():
        with Timer() as t:
            wavs, sr = run([text] * len(voices), [v for _, v in voices])
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
        "model": VARIANTS[args.variant], "load_s": round(t_load.s, 1), "sample_rate": sr, "clips": clips,
        "throughput": {"n": n, "batch": args.batch, "seconds": round(t_tp.s, 1), "clips_per_s": round(n / t_tp.s, 2)},
        "vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1),
    })


if __name__ == "__main__":
    main()
