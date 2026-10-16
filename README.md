# custom_wake_word

A lean, self-maintained training pipeline for custom [microWakeWord](https://github.com/kahrendt/microWakeWord)
models (ESPHome on-device wake words). It replaces the TaterTotterson trainer container for
day-to-day use.

Goals:

- Natural positive samples: voice-cloning TTS (OmniVoice) with hundreds of real reference voices, checked phonetically.
- Hard-negative mining: scan negative audio for false triggers and retrain with them.
- Content-hash caching per input set, so new personal or negative samples are always picked up.
- Profiles (`fast`, `thorough`).
- Output: ESPHome-valid manifest (`.json`) + `.tflite`.

Status: early. Web UI with projects, setup wizard, synthetic samples, sound-alikes, Sample Studio and training
(featurize, train, calibrate, ESPHome manifest + `.tflite` per run) works; mining and the export page are next.

## Web UI workflow

Everything is organised per wake word ("project"). The start page lists all projects; "New wake word"
opens a four-page wizard (name + language, TTS spellings, manifest credits, review). Inside a project
a step bar guides through the workflow, every step stays clickable and shows its status:

1. Wake word: settings (name, language, TTS spellings, author, website)
2. Synthetic samples: OmniVoice clones a random voice from the voice bank (or designs one from speaker
   attributes) per clip, with random tempo and punctuation. A multilingual phone recognizer
   (`facebook/wav2vec2-xlsr-53-espeak-cv-ft`) transcribes every clip into IPA and `trainer/tts/phonetic.py`
   compares it with the espeak-ng pronunciation of the spellings (weighted phone edit distance, onset x2.5,
   vocalized r cheap): Δ ≤ 0.30 positive, Δ ≥ 0.70 (and wake word not contained, ≥ 3 phones) negative
   candidate, gray zone dropped (~30 %). Background job with live progress, stop/continue and random
   listening for both sets. ~3-4 positive clips/s on the RTX 3090 (20k clips in ~1.5-2 h)

The pronunciation check (2 voices per spelling, phones + Δ) lives on the wake word page and in the wizard,
so spellings are verified before generating (`POST /api/tts/preview`, no project needed).
3. Own recordings: Sample Studio (optional, recommended)
4. Training (`trainer/train/`): one background job per run with live phases.
   - Sources (`sources.py`): synthetic positives (weight 2), own positives (3), sound-alikes (6, penalty 1.25),
     own negatives (8, 1.25), borrowed projects (4), shared VOiCES speech (12), CHiME-6 dinner party (12),
     no-speech (5), CHiME-6/DiPCo ambient for validation and test. Clips split 80/10/10 by a hash of their name.
   - Features (`featurize.py`): microWakeWord augmentation (RIR, background noise, EQ, ...) in a CPU pool, stored
     as uint16 (lossless, half of float32) and cropped to the 178 frames the model reads. Cached per corpus shard /
     WAV folder in `data/cache/features/<key>/`, keyed by content + feature version, shared across projects.
   - Training: microWakeWord `model_train_eval` (mixednet as in the old trainer, batch 16, lr 0.001, negative class
     weight 20) on the GPU (`mww_entry.py` refuses a CPU-only TF), profiles fast (10k steps) / thorough (40k), then the
     streaming int8 TFLite export.
   - Calibration (`calibrate.py`): the quantized streaming model runs over the test split and ~5 h ambient audio;
     cutoff + sliding window are picked for a target of false accepts per hour (default 0.25) with the old trainer's
     tier rule; recall per positive source and trigger rate per word-like negative source are reported.
   - Output per run in `projects/<slug>/runs/<id>/`: `<wake_word>.tflite`, `<wake_word>.json` (ESPHome manifest,
     allowed keys only), `run.json` (sources, validation history, calibration curve), `mww/` (checkpoints, logs).
5. Mining - planned, milestone 2 (optional)
6. Export (ESPHome manifest + `.tflite`) - planned, milestone 1

Opening a project jumps to the next open step.

## Layout

| Path | Purpose |
|---|---|
| `docker/Dockerfile` | Image with two venvs: `/opt/venv-train` (TF 2.21 + microWakeWord, CUDA 12 pip libs) and `/opt/venv-omni` (OmniVoice + wav2vec2 check, PyTorch, CUDA 13 pip libs) |
| `docker/requirements-*.in` | Direct dependencies (exact pins) |
| `docker/requirements-*.txt` | Fully resolved lock files (generated, see below) |
| `spikes/` | Throwaway experiments with measurements |
| `trainer/` | Python package: projects (`trainer/projects.py`), Sample Studio storage (`trainer/studio/`), FastAPI server (`trainer/server/`), pipeline (WIP) |
| `ui/` | Web UI "Wakeforge" (Vite + Svelte 5 + TypeScript) |
| `data/` | All datasets, caches, models and runs. Git-ignored, bind-mounted to `/app/data` |

Data layout below `data/`:

| Path | Content |
|---|---|
| `projects/<slug>/project.json` | Project settings: `wake_word`, `language`, `tts_phrases`, `confusables` (sound-alike negatives, see `trainer/tts/confusables.py`), `author`, `website`, `borrow_negatives` (other projects whose recordings and/or synthetic clips count as negatives here; referenced, not copied; refused when the wake words are within phone distance 0.35, see `trainer/projects.py`) |
| `projects/<slug>/recordings/<YYYYMMDD-HHMMSS>/` | Sample Studio takes: `recording.wav`, `clips/`, `clips.json`, `session.json` |
| `projects/<slug>/samples/positive/`, `.../negative/` | Sorted real clips (16 kHz mono PCM16). A clip's label is the folder holding its copy |
| `projects/<slug>/generated/tts/` | Synthetic corpus: `corpus.json` index + `shard-*.npz` (int16 clips concatenated, offsets, voice, phrase, speed/design/steps), see `trainer/tts/corpus.py` |
| `projects/<slug>/generated/tts-negative/` | Negative candidates: TTS clips that came out clearly different from every spelling (same format) |
| `projects/<slug>/generated/tts-confusable/` | Sound-alike negatives: the `confusables` spoken by the voice bank, minus clips that sounded like (or contained) the wake word (same format) |
| `cache/preview/<key>/` | Pronunciation check clips (last 20 checks) |
| `projects/<slug>/jobs/<YYYYMMDD-HHMMSS>-<kind>/` | Background job: `job.json` (command, pid), `progress.json` (written by the worker), `log.txt` |
| `projects/<slug>/runs/<YYYYMMDD-HHMMSS>-<profile>/` | Training run: model, manifest, `run.json`, `training_parameters.yaml`, `mww/` train dir |
| `cache/features/<key>/` | Cached spectrograms per corpus shard or WAV folder (`training/`, `validation/`, `testing/` RaggedMmaps + `done`) |
| `datasets/` | Shared negative feature sets and augmentation audio copied from the old trainer volume |
| `voices/<language>/` | Voice bank for cloning: `<id>.wav` (2.5-5 s, 24 kHz, cut at pauses) + `voices.json` (transcript, F0, gender, source). German: 300 voices (150 m / 150 f) from Kartoffelphon |
| `downloads/kartoffelphon/` | Kartoffelphon Arrow shards (German podcasts + LibriVox, CC-BY 4.0), source of the voice bank |
| `models/piper/` | Piper voices from the first spikes (unused by the pipeline) |

`python -m trainer.projects list` shows all projects. `python -m trainer.projects migrate --wake-word X`
moves a pre-project `data/recordings` + `data/samples` layout into a new project (already done for Dscharwis).

## Usage

```sh
cd ui && npm ci --before=YYYY-MM-DD && npm run build && cd ..
docker compose up -d --build
```

The container starts the API and UI on http://localhost:8790 (uvicorn with auto-reload on `trainer/`).
For UI development run `npm run dev` in `ui/` and open http://localhost:5173 (proxies `/api` to 8790).

Shell into the container:

```sh
docker exec -it cww-trainer bash
```

Inside the container, use the launchers `py-omni` (OmniVoice venv) and `py-train` (TF venv):

```sh
py-omni -m trainer.tts.voices build --language de --max 300     # voice bank, once per language
py-omni -m trainer.tts.omni run --project data/projects/dscharwis --job /tmp/job --count 20000
py-omni -m trainer.tts.omni preview --project data/projects/dscharwis --phrase Jarvis --out /tmp/preview
py-train spikes/featurize.py --input data/spikes/piper --output data/spikes/features/piper
py-train -m microwakeword.model_train_eval --training_config spikes/train_smoke.yaml ... mixednet ...
```

## Spike results (RTX 3090, 2026-10-15)

| Stage | Result |
|---|---|
| Piper `de_DE-mls-medium`, spike (batch 128, per-clip WAV) | ~260-320 samples/s inference, 45 samples/s end-to-end (serial resample + WAV write), ~5 % rejected; 50k in ~18 min (old trainer: 28 h) |
| Piper, former `trainer.tts.generate` (batch 64, tuned CUDA arena, vectorized resample in threads, npz shards; removed after Spike B, see commit 942b8f3) | ~240 clips/s end-to-end, ~4 % rejected; 50k in ~3.5 min, but unusable German audio |
| OmniVoice, `trainer.tts.omni` (batch 32, 16 steps, 2.5-5 s refs, IPA phone check) | ~3-4 positive clips/s, ~30 % gray zone, ~0.5 % negative candidates. TTS is ~98 % of the time; Whisper as the check was 75x slower than wav2vec2 CTC (30 s padding) and guessed real words |
| Sound-alikes, `trainer.tts.omni --mode confusable` (24 words, batch 32, 16 steps) | ~4.4 clips/s, ~5 % dropped as too close to the wake word; suggestions (letter edits + 3.6k voice-bank words, espeak in one batch) ~4 s |
| Phone check calibration (`spikes/phonetic_check.py`) | OmniVoice 79 % positive / 0 % negative, own recordings median Δ 0.24, random German speech 0 % positive / 88 % negative, Piper MLS 0 % positive, "Garvis" 0.33 / "Davis" 0.44 gray |
| Featurize 2k clips, 14 workers | 75 s (1600 train clips x2 reps x10 slides = 32k spectrograms, 1.5 GB float32) |
| Train 500 steps + streaming int8 TFLite export | ~3 min total |
| `trainer.train` featurize, warm pool (2026-10-16) | 17.7k new clips in 2.7 min (111 clips/s), cache 4.7 GB for 20k + 300 sound-alikes + 98 own |
| `trainer.train` thorough, 20k synthetic + 98 own + 300 sound-alikes | 40k steps ~35 min (18-19 steps/s incl. validation), run total 40 min. Test: recall 94.0 % at 0.19 FA/h (cutoff 0.86, window 8), sound-alikes trigger 10.7 % |
| Old Tater model (50k clips) on the same test set | recall 91.4 % at 0.19 FA/h (cutoff 0.98, window 3), sound-alikes trigger 53.6 % |
| `trainer.train` fast, 2.3k synthetic only | 10k steps, run total 20 min, recall 71 % at 0.19 FA/h |

### Spike B: German TTS quality (2026-10-15)

Piper `de_DE-mls-medium` turned out to be unusable for German wake words: the batched output is
numerically identical to Piper's own path, the voice itself produces gibberish for "Dscharwis"
(1/24 Whisper hits). The old Tater trainer used modern voice-cloning TTS (OmniVoice, Qwen3-TTS, MOSS).

`spikes/ttsb/` compares voice-cloning models with 10 German reference voices from Kartoffelphon
(`refs.py`), one venv per model under `/opt/spike/<name>` in the container, Whisper large-v3-turbo
scoring (`score_asr.py`: spelling regex or Kölner Phonetik match) and a listening page (`report.py`
-> `data/spikes/listen/index.html`).

| Model | Whisper hits | Clips/s (3090) | VRAM |
|---|---|---|---|
| OmniVoice clone (chosen, best by ear) | 29-30/30 | 1.3; 6.0 with 3 s refs + 16 steps | 5-9 GB |
| Qwen3-TTS 1.7B Base clone | 29/30 | 2.3-3.0 (HF generate) | 9-19 GB |
| Audio8 TTS 0.6B clone | 30/30 | 2.5-3.0 | 10-19 GB |
| OmniVoice voice design | 18/18 | 6.7 | 2 GB |
| VoxCPM2 clone + design | 37/48 | 1.0 (no batching) | 6 GB |
| Piper MLS / Thorsten | 1/24 / 4/4 | very fast | - |

Batch size beyond 16 does not raise throughput for any of them; reference length and diffusion steps do.

Open optimizations: cache background audio in RAM, store spectrograms as uint16 (half size),
fewer stored slide frames.

Piper on CUDA with varying output lengths: the default arena (power-of-two growth, max cuDNN workspace)
nearly fills the 24 GB at batch 128 and then stalls for minutes. `arena_extend_strategy=kSameAsRequested`
plus `cudnn_conv_use_max_workspace=0` at batch 64 gives a steady ~300/s (`spikes/piper_shapes.py`).

## Dependencies

Pin exact versions released at least 7 days ago. Lock files are generated with an
`--exclude-newer` cut-off date (today minus 7 days):

```sh
uv pip compile docker/requirements-train.in -o docker/requirements-train.txt \
  --python-version 3.12 --python-platform x86_64-manylinux_2_28 --exclude-newer YYYY-MM-DD
uv pip compile docker/requirements-omni.in -o docker/requirements-omni.txt \
  --python-version 3.12 --python-platform x86_64-manylinux_2_28 --exclude-newer YYYY-MM-DD
```

## Notes

- The CUDA pip libs are not found automatically by TF (`libcusolver.so.11`; onnxruntime-gpu had the same
  issue with `libcublasLt.so.13`). The `py-train`/`py-omni` launchers set `LD_LIBRARY_PATH` per venv.
- The Piper venv (`py-tts`) left the image after Spike B; the Piper spikes need the image of commit eb63b98.
- microWakeWord's `audio/` and `layers/` have no `__init__.py`, so a plain pip install drops them;
  the Dockerfile clones the pinned commit and adds them. TensorBoard is required for `tf.summary`.
- Piper MLS speakers read slowly: at `length_scale=1` "Dscharwis" takes ~1.4 s (median) and
  high `noise_w` produces multi-second outliers. The spike uses `length_scale` 0.55-1.0 and
  `noise_w` 0.2-0.5.
- Piper voice `de_DE-mls-medium` has 236 speakers, but its ONNX export fixes the `sid` input
  to batch size 1. `spikes/piper_throughput.py` patches the graph so `sid` is batched and
  exposes the per-phoneme durations (`w_ceil`) to crop padded rows to their real length.
- ESPHome manifests may only contain: `type`, `wake_word`, `author`, `website`, `model`,
  `trained_languages`, `version` (2) and `micro{probability_cutoff, sliding_window_size,
  feature_step_size, tensor_arena_size, minimum_esphome_version}`.
