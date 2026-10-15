# custom_wake_word

A lean, self-maintained training pipeline for custom [microWakeWord](https://github.com/kahrendt/microWakeWord)
models (ESPHome on-device wake words). It replaces the TaterTotterson trainer container for
day-to-day use.

Goals:

- Fast positive sample generation (batched multi-speaker TTS on GPU).
- Hard-negative mining: scan negative audio for false triggers and retrain with them.
- Content-hash caching per input set, so new personal or negative samples are always picked up.
- Profiles (`fast`, `thorough`).
- Output: ESPHome-valid manifest (`.json`) + `.tflite`.

Status: early. Web UI with projects, setup wizard, synthetic sample generation and Sample Studio works;
featurize/train/export are still spikes (`spikes/`).

## Web UI workflow

Everything is organised per wake word ("project"). The start page lists all projects; "New wake word"
opens a four-page wizard (name + language, TTS spellings, manifest credits, review). Inside a project
a step bar guides through the workflow, every step stays clickable and shows its status:

1. Wake word: settings (name, language, TTS spellings, author, website)
2. Synthetic samples: batched multi-speaker Piper on the GPU as a background job (live progress,
   stop/continue, pronunciation preview per spelling, random listening). Voices: de, en, fr, nl
   (`trainer/tts/catalog.py`)
3. Own recordings: Sample Studio (optional, recommended)
4. Training - planned, milestone 1
5. Mining - planned, milestone 2 (optional)
6. Export (ESPHome manifest + `.tflite`) - planned, milestone 1

Opening a project jumps to the next open step.

## Layout

| Path | Purpose |
|---|---|
| `docker/Dockerfile` | Image with two venvs: `/opt/venv-train` (TF 2.21 + microWakeWord, CUDA 12 pip libs) and `/opt/venv-tts` (Piper + onnxruntime-gpu, CUDA 13 pip libs) |
| `docker/requirements-*.in` | Direct dependencies (exact pins) |
| `docker/requirements-*.txt` | Fully resolved lock files (generated, see below) |
| `spikes/` | Throwaway experiments with measurements |
| `trainer/` | Python package: projects (`trainer/projects.py`), Sample Studio storage (`trainer/studio/`), FastAPI server (`trainer/server/`), pipeline (WIP) |
| `ui/` | Web UI "Wakeforge" (Vite + Svelte 5 + TypeScript) |
| `data/` | All datasets, caches, models and runs. Git-ignored, bind-mounted to `/app/data` |

Data layout below `data/`:

| Path | Content |
|---|---|
| `projects/<slug>/project.json` | Project settings: `wake_word`, `language`, `tts_phrases`, `author`, `website` |
| `projects/<slug>/recordings/<YYYYMMDD-HHMMSS>/` | Sample Studio takes: `recording.wav`, `clips/`, `clips.json`, `session.json` |
| `projects/<slug>/samples/positive/`, `.../negative/` | Sorted real clips (16 kHz mono PCM16). A clip's label is the folder holding its copy |
| `projects/<slug>/generated/tts/` | Synthetic corpus: `corpus.json` index + `shard-*.npz` (int16 clips concatenated, offsets, speaker, phrase, scales), see `trainer/tts/corpus.py` |
| `projects/<slug>/generated/preview/` | Last pronunciation previews per spelling |
| `projects/<slug>/jobs/<YYYYMMDD-HHMMSS>-<kind>/` | Background job: `job.json` (command, pid), `progress.json` (written by the worker), `log.txt` |
| `projects/<slug>/runs/`, `models/` | Training runs, exported models (planned) |
| `datasets/` | Shared negative feature sets and augmentation audio copied from the old trainer volume |
| `models/piper/` | Shared Piper voices (incl. the batched-`sid` ONNX patch) |

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

Inside the container, use the launchers `py-tts` (Piper venv) and `py-train` (TF venv):

```sh
py-tts -m trainer.tts.generate run --project data/projects/dscharwis --job /tmp/job --count 50000
py-tts -m trainer.tts.generate preview --project data/projects/dscharwis --phrase Dscharwis --out /tmp/preview
py-train spikes/featurize.py --input data/spikes/piper --output data/spikes/features/piper
py-train -m microwakeword.model_train_eval --training_config spikes/train_smoke.yaml ... mixednet ...
```

## Spike results (RTX 3090, 2026-10-15)

| Stage | Result |
|---|---|
| Piper `de_DE-mls-medium`, spike (batch 128, per-clip WAV) | ~260-320 samples/s inference, 45 samples/s end-to-end (serial resample + WAV write), ~5 % rejected; 50k in ~18 min (old trainer: 28 h) |
| Piper, `trainer.tts.generate` (batch 64, tuned CUDA arena, vectorized resample in threads, npz shards) | ~240 clips/s end-to-end, ~4 % rejected; 50k in ~3.5 min. Inference is ~95 % of the time |
| Featurize 2k clips, 14 workers | 75 s (1600 train clips x2 reps x10 slides = 32k spectrograms, 1.5 GB float32) |
| Train 500 steps + streaming int8 TFLite export | ~3 min total |

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
uv pip compile docker/requirements-tts.in -o docker/requirements-tts.txt \
  --python-version 3.12 --python-platform x86_64-manylinux_2_28 --exclude-newer YYYY-MM-DD
```

## Notes

- The CUDA pip libs are not found automatically, neither by TF (`libcusolver.so.11`) nor by
  onnxruntime-gpu (`libcublasLt.so.13`). The `py-train`/`py-tts` launchers set `LD_LIBRARY_PATH` per venv.
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
