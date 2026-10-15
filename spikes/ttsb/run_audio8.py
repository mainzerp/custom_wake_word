"""Spike B: Audio8 TTS Preview 0.6B (zero-shot cloning, batched).

  docker exec -e PYTHONPATH=/app -e HF_HOME=/app/data/cache/huggingface cww-trainer \
    /opt/spike/audio8/bin/python spikes/ttsb/run_audio8.py
"""

import argparse
import random

import torch
from transformers import AutoModel, AutoProcessor

from spikes.ttsb.common import TEXTS, THROUGHPUT_N, Timer, out_dir, refs, save, write_result

MODEL = "Audio8/Audio8-TTS-Preview-0.6b"
GEN = {"max_new_tokens": 220, "temperature": 0.8, "top_p": 0.95, "top_k": 50, "do_sample": True}  # ~21.5 frames/s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    with Timer() as t_load:
        processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
        model = AutoModel.from_pretrained(MODEL, trust_remote_code=True, dtype=torch.bfloat16).eval().to("cuda")
    sr = model.config.codec_sample_rate

    def run(texts, rs):
        inputs = processor(text=texts, reference_audio=[r["path"] for r in rs], reference_text=[r["text"] for r in rs],
                           return_tensors="pt")
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
        with torch.inference_mode():
            out = model.generate(**inputs, **GEN, return_dict_in_generate=True)
            wavs, lens = model.decode_audio(out.codes)
        return [wavs[i, : int(lens[i])].float().cpu().numpy() for i in range(len(texts))]

    rs = refs()
    d = out_dir("audio8")
    clips = []
    for key, text in TEXTS.items():
        with Timer() as t:
            wavs = run([text] * len(rs), rs)
        for r, w in zip(rs, wavs):
            clips.append({"file": f"{r['id']}_{key}.wav", "voice": r["id"], "text": text,
                          "seconds": save(d, f"{r['id']}_{key}", w, sr), "batch_s": round(t.s, 2)})

    rng = random.Random(0)
    torch.cuda.synchronize()
    with Timer() as t_tp:
        n = 0
        while n < THROUGHPUT_N:
            batch = [rng.choice(rs) for _ in range(args.batch)]
            run([TEXTS["jarvis"]] * len(batch), batch)
            n += len(batch)
    write_result("audio8", {
        "model": MODEL, "load_s": round(t_load.s, 1), "sample_rate": sr, "clips": clips,
        "throughput": {"n": n, "batch": args.batch, "seconds": round(t_tp.s, 1), "clips_per_s": round(n / t_tp.s, 2)},
        "vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1),
    })


if __name__ == "__main__":
    main()
