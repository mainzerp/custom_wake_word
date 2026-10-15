"""Batched multi-speaker Piper generation on the GPU (runs in the TTS venv).

  py-tts -m trainer.tts.generate run --project data/projects/x --job <job dir> --count 50000
  py-tts -m trainer.tts.generate preview --project data/projects/x --phrase Dscharwis --out <dir>

`run` is resumable: it tops the corpus up to --count clips. SIGTERM stops after the current batch,
flushing everything generated so far. Progress goes to <job dir>/progress.json.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import soundfile as sf
from piper import PiperVoice
from piper.patch_voice_with_alignment import add_alignment_output
from scipy.signal import resample_poly

from trainer.paths import PIPER_MODELS
from trainer.tts import corpus
from trainer.tts.catalog import voice_for

SHARD_SIZE = 1024
ort.set_default_logger_severity(3)


def ensure_voice(language: str) -> tuple[str, Path]:
    voice = voice_for(language)
    if not voice:
        raise RuntimeError(f"no multi-speaker Piper voice configured for language {language!r}")
    PIPER_MODELS.mkdir(parents=True, exist_ok=True)
    for suffix in (".onnx", ".onnx.json"):
        dest = PIPER_MODELS / f"{voice['name']}{suffix}"
        if not dest.exists():
            print(f"downloading {dest.name}", flush=True)
            tmp = dest.with_name(dest.name + ".part")
            urllib.request.urlretrieve(voice["url"] + suffix, tmp)
            os.replace(tmp, dest)
    return voice["name"], PIPER_MODELS / f"{voice['name']}.onnx"


def batched_session(model: Path) -> ort.InferenceSession:
    """Piper exports `sid` with a fixed batch dim of 1; relax it so each row gets its own speaker.
    Also expose per-phoneme durations so padded rows can be cropped to their true length."""
    patched = model.with_suffix(".batch.onnx")
    if not patched.exists():
        m = onnx.load(str(model))
        for inp in m.graph.input:
            if inp.name == "sid":
                inp.type.tensor_type.shape.dim[0].dim_param = "batch_size"
        add_alignment_output(m)
        tmp = patched.with_name(patched.name + ".part")
        onnx.save(m, str(tmp))
        os.replace(tmp, patched)
    # Output length varies per batch. The default arena (power-of-two growth, max cuDNN workspace) then
    # approaches 24 GB at batch 128 and stalls for minutes; see spikes/piper_shapes.py.
    options = {"cudnn_conv_algo_search": "HEURISTIC", "arena_extend_strategy": "kSameAsRequested",
               "cudnn_conv_use_max_workspace": "0"}
    session = ort.InferenceSession(str(patched), providers=[("CUDAExecutionProvider", options)])
    if "CUDAExecutionProvider" not in session.get_providers():
        raise RuntimeError("CUDAExecutionProvider failed to load; refusing to fall back to CPU")
    return session


class Synth:
    def __init__(self, language: str):
        self.voice_name, model = ensure_voice(language)
        self.voice = PiperVoice.load(model)
        self.session = batched_session(model)
        self.rate = self.voice.config.sample_rate
        self.hop = self.voice.config.hop_length
        self.speakers = self.voice.config.num_speakers
        g = np.gcd(corpus.SAMPLE_RATE, self.rate)
        self.up, self.down = corpus.SAMPLE_RATE // g, self.rate // g

    def ids(self, phrase: str) -> np.ndarray:
        ids = [i for sentence in self.voice.phonemize(phrase) for i in self.voice.phonemes_to_ids(sentence)]
        if not ids:
            raise ValueError(f"phrase produced no phonemes: {phrase!r}")
        return np.array(ids, dtype=np.int64)

    def infer(self, ids: np.ndarray, speakers: np.ndarray, scales: list[float]) -> tuple[np.ndarray, np.ndarray]:
        n = len(speakers)
        audio, widths = self.session.run(None, {
            "input": np.tile(ids, (n, 1)),
            "input_lengths": np.full(n, len(ids), dtype=np.int64),
            "scales": np.array(scales, dtype=np.float32),
            "sid": speakers.astype(np.int64),
        })
        lengths = widths.reshape(n, -1).sum(axis=1).astype(np.int64) * self.hop
        return audio.reshape(n, -1), lengths

    def postprocess(self, audio: np.ndarray, lengths: np.ndarray, min_s: float, max_s: float) -> list[np.ndarray | None]:
        """Resample the padded batch in one vectorized call, then crop, trim and peak-normalize each row."""
        resampled = resample_poly(audio, self.up, self.down, axis=1).astype(np.float32)
        out = []
        for row, length in zip(resampled, lengths * self.up // self.down):
            clip = trim(row[:length])
            seconds = len(clip) / corpus.SAMPLE_RATE
            out.append(clip / np.abs(clip).max() * 0.9 if min_s <= seconds <= max_s else None)
        return out


def trim(audio: np.ndarray, rel_threshold: float = 0.05, pad: int = 1600) -> np.ndarray:
    if not audio.size:
        return audio
    idx = np.flatnonzero(np.abs(audio) > rel_threshold * np.abs(audio).max())
    if idx.size == 0:
        return audio[:0]
    return audio[max(idx[0] - pad, 0):idx[-1] + pad]


class SpeakerCycle:
    """Draw speakers in shuffled rounds so every speaker is used equally often."""

    def __init__(self, n: int, rng: np.random.Generator):
        self.n, self.rng, self.pool = n, rng, []

    def take(self, k: int) -> np.ndarray:
        while len(self.pool) < k:
            self.pool.extend(self.rng.permutation(self.n).tolist())
        out, self.pool = self.pool[:k], self.pool[k:]
        return np.array(out)


def write_progress(job: Path, **data) -> None:
    data["updated"] = time.time()
    tmp = job / "progress.json.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, job / "progress.json")


def run(args: argparse.Namespace) -> None:
    stop = False

    def on_term(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    project_dir = Path(args.project)
    project = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    phrases = project["tts_phrases"] or [project["wake_word"]]
    out = corpus.corpus_dir(project_dir)
    index = corpus.load_index(out)
    start = index["total"]
    progress = {"state": "running", "done": start, "start": start, "total": args.count, "rejected": 0, "rate": 0.0}
    write_progress(args.job, **progress, message="loading voice")

    synth = Synth(project["language"])
    if index["voice"] and index["voice"] != synth.voice_name:
        raise RuntimeError(f"corpus was generated with {index['voice']}; reset it before using {synth.voice_name}")
    index["voice"] = synth.voice_name
    for p in phrases:
        if p not in index["phrases"]:
            index["phrases"].append(p)
    phrase_ids = [(index["phrases"].index(p), synth.ids(p)) for p in phrases]
    print(f"voice {synth.voice_name}: {synth.speakers} speakers, providers {synth.session.get_providers()}", flush=True)

    rng = np.random.default_rng([int(time.time()), start])
    speakers = SpeakerCycle(synth.speakers, rng)
    pool = ThreadPoolExecutor(max_workers=4)
    pending: deque = deque()
    buf: dict[str, list] = {"clips": [], "speaker": [], "phrase": [], "scales": []}
    done, rejected, t0, batch_no = start, 0, time.perf_counter(), 0
    timing = {"infer": 0.0, "wait": 0.0, "write": 0.0}

    def flush() -> None:
        if buf["clips"]:
            t = time.perf_counter()
            corpus.append_shard(out, index, buf["clips"], buf["speaker"], buf["phrase"], buf["scales"])
            timing["write"] += time.perf_counter() - t
            for v in buf.values():
                v.clear()

    def collect(item) -> None:
        nonlocal done, rejected
        future, spk, phrase, scales = item
        t = time.perf_counter()
        clips = future.result()
        timing["wait"] += time.perf_counter() - t
        for clip, s in zip(clips, spk):
            if done >= args.count:
                break
            if clip is None:
                rejected += 1
                continue
            buf["clips"].append(clip)
            buf["speaker"].append(int(s))
            buf["phrase"].append(phrase)
            buf["scales"].append(scales)
            done += 1
        if len(buf["clips"]) >= SHARD_SIZE:
            flush()
        rate = (done - start) / (time.perf_counter() - t0)
        write_progress(args.job, **{**progress, "done": done, "rejected": rejected, "rate": round(rate, 1),
                                    "eta": round((args.count - done) / rate) if rate else None})

    # Inference runs on the main thread while up to 4 earlier batches are post-processed in threads.
    # Rejected clips leave gaps, so keep going until the corpus really holds --count clips.
    while not stop and done < args.count:
        if done + sum(len(p[1]) for p in pending) >= args.count:
            collect(pending.popleft())
            continue
        phrase, ids = phrase_ids[batch_no % len(phrase_ids)]
        batch_no += 1
        spk = speakers.take(args.batch)
        scales = [float(rng.uniform(*args.noise_scale)), float(rng.uniform(*args.length_scale)), float(rng.uniform(*args.noise_w))]
        t = time.perf_counter()
        audio, lengths = synth.infer(ids, spk, scales)
        timing["infer"] += time.perf_counter() - t
        pending.append((pool.submit(synth.postprocess, audio, lengths, args.min_seconds, args.max_seconds), spk, phrase, scales))
        while len(pending) > 3 or (pending and pending[0][0].done()):
            collect(pending.popleft())
    while pending:
        collect(pending.popleft())
    flush()
    state = "stopped" if stop and done < args.count else "done"
    write_progress(args.job, **{**progress, "state": state, "done": done, "rejected": rejected,
                                "rate": round((done - start) / (time.perf_counter() - t0), 1), "eta": 0})
    print(f"{state}: {done} clips ({done - start} new, {rejected} rejected) in {time.perf_counter() - t0:.0f}s, "
          + ", ".join(f"{k} {v:.1f}s" for k, v in timing.items()), flush=True)


def preview(args: argparse.Namespace) -> None:
    project = json.loads((Path(args.project) / "project.json").read_text(encoding="utf-8"))
    synth = Synth(project["language"])
    rng = np.random.default_rng()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    spk = rng.choice(synth.speakers, size=args.n, replace=False)
    scales = [0.55, float(np.mean(args.length_scale)), 0.35]
    audio, lengths = synth.infer(synth.ids(args.phrase), spk, scales)
    resampled = resample_poly(audio, synth.up, synth.down, axis=1).astype(np.float32)
    clips = []
    for i, (row, length, s) in enumerate(zip(resampled, lengths * synth.up // synth.down, spk)):
        clip = trim(row[:length])
        if clip.size:
            sf.write(out / f"{i}.wav", clip / np.abs(clip).max() * 0.9, corpus.SAMPLE_RATE, subtype="PCM_16")
            clips.append({"file": f"{i}.wav", "speaker": int(s), "seconds": round(len(clip) / corpus.SAMPLE_RATE, 2)})
    print(json.dumps({"voice": synth.voice_name, "clips": clips}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "preview"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--length-scale", type=float, nargs=2, default=[0.55, 1.0])
    r = sub.choices["run"]
    r.add_argument("--job", type=Path, required=True)
    r.add_argument("--count", type=int, required=True)
    r.add_argument("--batch", type=int, default=64)
    r.add_argument("--noise-scale", type=float, nargs=2, default=[0.3, 0.8])
    r.add_argument("--noise-w", type=float, nargs=2, default=[0.2, 0.5])
    r.add_argument("--min-seconds", type=float, default=0.3)
    r.add_argument("--max-seconds", type=float, default=2.0)
    pv = sub.choices["preview"]
    pv.add_argument("--phrase", required=True)
    pv.add_argument("--out", required=True)
    pv.add_argument("--n", type=int, default=6)
    args = parser.parse_args()
    if args.command == "preview":
        preview(args)
        return
    try:
        run(args)
    except Exception as e:
        write_progress(args.job, state="failed", message=f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
