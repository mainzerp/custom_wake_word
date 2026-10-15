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

Status: early. Web UI with Sample Studio works; pipeline stages are spikes (`spikes/`).

## Layout

| Path | Purpose |
|---|---|
| `docker/Dockerfile` | Image with two venvs: `/opt/venv-train` (TF 2.21 + microWakeWord, CUDA 12 pip libs) and `/opt/venv-tts` (Piper + onnxruntime-gpu, CUDA 13 pip libs) |
| `docker/requirements-*.in` | Direct dependencies (exact pins) |
| `docker/requirements-*.txt` | Fully resolved lock files (generated, see below) |
| `spikes/` | Throwaway experiments with measurements |
| `trainer/` | Python package: pipeline (WIP), Sample Studio storage (`trainer/studio/`), FastAPI server (`trainer/server/`) |
| `ui/` | Web UI "Wakeforge" (Vite + Svelte 5 + TypeScript) |
| `data/` | All datasets, caches, models and runs. Git-ignored, bind-mounted to `/app/data` |

Data layout below `data/`:

| Path | Content |
|---|---|
| `recordings/<YYYYMMDD-HHMMSS>/` | Sample Studio takes: `recording.wav`, `clips/`, `clips.json`, `session.json` |
| `samples/positive/`, `samples/negative/` | Sorted real clips (16 kHz mono PCM16). A clip's label is the folder holding its copy |
| `datasets/` | Negative feature sets and augmentation audio copied from the old trainer volume |

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
py-tts spikes/piper_throughput.py --phrase Dscharwis --count 2000 --batch 128
py-train spikes/featurize.py --input data/spikes/piper --output data/spikes/features/piper
py-train -m microwakeword.model_train_eval --training_config spikes/train_smoke.yaml ... mixednet ...
```

## Spike results (RTX 3090, 2026-10-15)

| Stage | Result |
|---|---|
| Piper `de_DE-mls-medium`, batch 128, GPU | ~260-320 samples/s inference, 45 samples/s end-to-end (serial resample + WAV write), ~5 % rejected; 50k in ~18 min (old trainer: 28 h) |
| Featurize 2k clips, 14 workers | 75 s (1600 train clips x2 reps x10 slides = 32k spectrograms, 1.5 GB float32) |
| Train 500 steps + streaming int8 TFLite export | ~3 min total |

Open optimizations: parallel resample/write, cache background audio in RAM, store spectrograms
as uint16 (half size), fewer stored slide frames.

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
