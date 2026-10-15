"""Synthetic wake word positives with OmniVoice voice cloning (runs in the OmniVoice venv).

  py-omni -m trainer.tts.omni run --project data/projects/x --job <job dir> --count 20000
  py-omni -m trainer.tts.omni preview --project data/projects/x --phrase Jarvis --out <dir>

Every clip clones a random reference voice from the bank (data/voices/<language>/) or, for --design-share of the
batches, a voice designed from speaker attributes. Tempo and punctuation vary per clip. A character CTC model
transcribes each clip and drops it unless it sounds like one of the project's spellings (trainer.tts.match).

`run` is resumable: it tops the corpus up to --count clips. SIGTERM stops after the current batch.
Progress goes to <job dir>/progress.json.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import signal
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly

from trainer.tts import corpus
from trainer.tts.match import contains_wake_word
from trainer.tts.voices import load_bank, voice_dir

ENGINE = "omnivoice"
MODEL = "k2-fsa/OmniVoice"
SHARD_SIZE = 1024
# Character CTC models transcribe phonetically ("tscharfis", "chawis") at ~400 clips/s, where Whisper pads every
# clip to 30 s (~15 clips/s) and guesses real words ("JavaScript").
ASR_MODELS = {
    "de": "jonatasgrosman/wav2vec2-large-xlsr-53-german",
    "en": "jonatasgrosman/wav2vec2-large-xlsr-53-english",
    "fr": "jonatasgrosman/wav2vec2-large-xlsr-53-french",
    "nl": "jonatasgrosman/wav2vec2-large-xlsr-53-dutch",
    "es": "jonatasgrosman/wav2vec2-large-xlsr-53-spanish",
    "it": "jonatasgrosman/wav2vec2-large-xlsr-53-italian",
}
PUNCTUATION = [(".", 0.5), ("!", 0.25), ("?", 0.15), ("", 0.1)]
DESIGN_ATTRS = {
    "gender": ["male", "female"],
    "age": ["child", "teenager", "young adult", "middle-aged", "elderly"],
    "pitch": ["very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch"],
}


def write_progress(job: Path, **data) -> None:
    data["updated"] = time.time()
    tmp = job / "progress.json.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, job / "progress.json")


class Cycle:
    """Draw items in shuffled rounds so every one is used equally often."""

    def __init__(self, items: list, rng: random.Random):
        self.items, self.rng, self.pool = items, rng, []

    def take(self, k: int) -> list:
        while len(self.pool) < k:
            batch = list(range(len(self.items)))
            self.rng.shuffle(batch)
            self.pool.extend(batch)
        out, self.pool = self.pool[:k], self.pool[k:]
        return out


class Synth:
    def __init__(self, language: str, steps: int, with_asr: bool):
        from omnivoice import OmniVoice, OmniVoiceGenerationConfig

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available; refusing to run OmniVoice on the CPU")
        self.language = language
        self.model = OmniVoice.from_pretrained(MODEL, device_map="cuda:0", dtype=torch.float16)
        self.config = OmniVoiceGenerationConfig(num_step=steps)
        self.rate = self.model.sampling_rate
        g = np.gcd(corpus.SAMPLE_RATE, self.rate)
        self.up, self.down = corpus.SAMPLE_RATE // g, self.rate // g
        self.bank = load_bank(language)
        self.prompts = [self.model.create_voice_clone_prompt(ref_audio=str(voice_dir(language) / f"{v['id']}.wav"),
                                                             ref_text=v["text"]) for v in self.bank]
        self.asr = None
        if with_asr and language in ASR_MODELS:
            from transformers import AutoModelForCTC, Wav2Vec2Processor

            self.asr_processor = Wav2Vec2Processor.from_pretrained(ASR_MODELS[language])
            self.asr = AutoModelForCTC.from_pretrained(ASR_MODELS[language], dtype=torch.float16).to("cuda").eval()
        elif with_asr:
            print(f"no phonetic check model for language {language!r}; clips are not filtered", flush=True)

    def generate(self, texts: list[str], speeds: list[float], prompts=None, instructs=None) -> list[np.ndarray]:
        wavs = self.model.generate(text=texts, language=self.language, speed=speeds, voice_clone_prompt=prompts,
                                   instruct=instructs, generation_config=self.config)
        out = []
        for w in wavs:
            w = np.asarray(w, dtype=np.float32).squeeze()
            out.append(corpus.trim(resample_poly(w, self.up, self.down).astype(np.float32)))
        return out

    def transcribe(self, clips: list[np.ndarray]) -> list[str]:
        if self.asr is None:
            return [""] * len(clips)
        if not clips:
            return []
        inp = self.asr_processor(clips, sampling_rate=corpus.SAMPLE_RATE, return_tensors="pt", padding=True)
        with torch.inference_mode():
            logits = self.asr(inp.input_values.to("cuda", torch.float16),
                              attention_mask=inp.attention_mask.to("cuda")).logits
        return [t.strip() for t in self.asr_processor.batch_decode(logits.argmax(-1))]


def design_voices() -> list[str]:
    return [f"{g}, {a}, {p}" for g in DESIGN_ATTRS["gender"] for a in DESIGN_ATTRS["age"] for p in DESIGN_ATTRS["pitch"]
            if not (a == "child" and p in ("very low pitch", "low pitch"))]


def with_punctuation(phrase: str, rng: random.Random) -> str:
    marks, weights = zip(*PUNCTUATION)
    return phrase.rstrip(".!?") + rng.choices(marks, weights)[0]


def load_project(path: Path) -> dict:
    project = json.loads((path / "project.json").read_text(encoding="utf-8"))
    project["phrases"] = project.get("tts_phrases") or [project["wake_word"]]
    return project


def run(args: argparse.Namespace) -> None:
    stop = False

    def on_term(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    project_dir = Path(args.project)
    project = load_project(project_dir)
    phrases = project["phrases"]
    out = corpus.corpus_dir(project_dir)
    index = corpus.load_index(out)
    if index["voice"] not in (None, ENGINE):
        raise RuntimeError(f"corpus was generated with {index['voice']}; reset it before using {ENGINE}")
    start = index["total"]
    progress = {"state": "running", "done": start, "start": start, "total": args.count, "rejected": 0, "filtered": 0,
                "rate": 0.0}
    write_progress(args.job, **progress, message="loading OmniVoice and the phonetic check")

    synth = Synth(project["language"], args.steps, not args.no_filter)
    designs = design_voices()
    index["voice"] = ENGINE
    index.setdefault("voices", [])
    for p in phrases:
        if p not in index["phrases"]:
            index["phrases"].append(p)
    names = [f"bank:{v['id']}" for v in synth.bank] + [f"design:{d}" for d in designs]
    for n in names:
        if n not in index["voices"]:
            index["voices"].append(n)
    voice_pos = {n: i for i, n in enumerate(index["voices"])}
    print(f"OmniVoice ready: {len(synth.bank)} bank voices, {len(designs)} designs, phrases {phrases}, "
          f"steps {args.steps}, filter {'off' if args.no_filter else 'on'}", flush=True)
    if not synth.bank and args.design_share < 1:
        print("no voice bank for this language, using voice design only", flush=True)

    rng = random.Random(f"{time.time()}-{start}")
    bank_cycle, design_cycle = Cycle(synth.bank, rng), Cycle(designs, rng)
    buf: dict[str, list] = {"clips": [], "speaker": [], "phrase": [], "scales": []}
    done, rejected, filtered, batch_no, t0 = start, 0, 0, 0, time.perf_counter()
    timing = {"tts": 0.0, "asr": 0.0, "write": 0.0}

    def flush() -> None:
        if buf["clips"]:
            t = time.perf_counter()
            corpus.append_shard(out, index, buf["clips"], buf["speaker"], buf["phrase"], buf["scales"])
            timing["write"] += time.perf_counter() - t
            for v in buf.values():
                v.clear()

    def collect(batch: list[tuple]) -> None:
        nonlocal done, filtered
        t = time.perf_counter()
        transcripts = synth.transcribe([b[0] for b in batch])
        timing["asr"] += time.perf_counter() - t
        for (clip, voice, phrase, speed, design), text in zip(batch, transcripts):
            if done >= args.count:
                break
            if synth.asr is not None and not contains_wake_word(text, phrases):
                filtered += 1
                continue
            buf["clips"].append(clip / np.abs(clip).max() * 0.9)
            buf["speaker"].append(voice_pos[voice])
            buf["phrase"].append(index["phrases"].index(phrase))
            buf["scales"].append([speed, 1.0 if design else 0.0, float(args.steps)])
            done += 1
        if len(buf["clips"]) >= SHARD_SIZE:
            flush()
        rate = (done - start) / (time.perf_counter() - t0)
        write_progress(args.job, **{**progress, "done": done, "rejected": rejected, "filtered": filtered,
                                    "rate": round(rate, 2), "eta": round((args.count - done) / rate) if rate else None})

    while not stop and done < args.count:
        batch_no += 1
        design = not synth.bank or rng.random() < args.design_share
        n = args.batch
        chosen = [phrases[rng.randrange(len(phrases))] for _ in range(n)]
        texts = [with_punctuation(p, rng) for p in chosen]
        speeds = [round(rng.uniform(*args.speed), 3) for _ in range(n)]
        if design:
            picks = design_cycle.take(n)
            voice_names = [f"design:{designs[i]}" for i in picks]
            kw = {"instructs": [designs[i] for i in picks]}
        else:
            picks = bank_cycle.take(n)
            voice_names = [f"bank:{synth.bank[i]['id']}" for i in picks]
            kw = {"prompts": [synth.prompts[i] for i in picks]}
        t = time.perf_counter()
        clips = synth.generate(texts, speeds, **kw)
        timing["tts"] += time.perf_counter() - t
        batch = [(c, voice_names[i], chosen[i], speeds[i], design) for i, c in enumerate(clips)
                 if args.min_seconds <= len(c) / corpus.SAMPLE_RATE <= args.max_seconds]
        rejected += n - len(batch)
        collect(batch)
        if batch_no % 20 == 0:
            print(f"{done}/{args.count} {(done - start) / (time.perf_counter() - t0):.1f} clips/s, "
                  f"rejected {rejected}, filtered {filtered}", flush=True)
    flush()
    state = "stopped" if stop and done < args.count else "done"
    elapsed = time.perf_counter() - t0
    write_progress(args.job, **{**progress, "state": state, "done": done, "rejected": rejected, "filtered": filtered,
                                "rate": round((done - start) / elapsed, 2), "eta": 0})
    print(f"{state}: {done} clips ({done - start} new, {rejected} rejected by length, {filtered} by the phonetic check) in "
          f"{elapsed:.0f}s, " + ", ".join(f"{k} {v:.1f}s" for k, v in timing.items()), flush=True)


def preview(args: argparse.Namespace) -> None:
    project = load_project(Path(args.project))
    synth = Synth(project["language"], args.steps, True)
    rng = random.Random()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n_design = 2 if synth.bank else args.n
    bank_picks = rng.sample(range(len(synth.bank)), min(args.n - n_design, len(synth.bank)))
    designs = rng.sample(design_voices(), n_design)
    labels, clips = [], []
    if bank_picks:
        speeds = [round(rng.uniform(*args.speed), 2) for _ in bank_picks]
        clips += synth.generate([args.phrase] * len(bank_picks), speeds, prompts=[synth.prompts[i] for i in bank_picks])
        labels += [(synth.bank[i]["id"], s) for i, s in zip(bank_picks, speeds)]
    speeds = [round(rng.uniform(*args.speed), 2) for _ in designs]
    clips += synth.generate([args.phrase] * len(designs), speeds, instructs=designs)
    labels += [(d, s) for d, s in zip(designs, speeds)]
    transcripts = synth.transcribe(clips)
    result = []
    for i, ((voice, speed), clip, text) in enumerate(zip(labels, clips, transcripts)):
        if not clip.size:
            continue
        sf.write(out / f"{i}.wav", clip / np.abs(clip).max() * 0.9, corpus.SAMPLE_RATE, subtype="PCM_16")
        result.append({"file": f"{i}.wav", "voice": voice, "speed": speed, "seconds": round(len(clip) / corpus.SAMPLE_RATE, 2),
                       "transcript": text, "hit": contains_wake_word(text, project["phrases"] + [args.phrase])})
    print(json.dumps({"engine": ENGINE, "clips": result}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "preview"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--steps", type=int, default=16)
        p.add_argument("--speed", type=float, nargs=2, default=[0.85, 1.2])
    r = sub.choices["run"]
    r.add_argument("--job", type=Path, required=True)
    r.add_argument("--count", type=int, required=True)
    r.add_argument("--batch", type=int, default=32)
    r.add_argument("--design-share", type=float, default=0.15)
    r.add_argument("--no-filter", action="store_true")
    r.add_argument("--min-seconds", type=float, default=0.3)
    r.add_argument("--max-seconds", type=float, default=2.0)
    pv = sub.choices["preview"]
    pv.add_argument("--phrase", required=True)
    pv.add_argument("--out", required=True)
    pv.add_argument("--n", type=int, default=8)
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
