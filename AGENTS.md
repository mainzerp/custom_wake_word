# Agent notes

- Talk to the user in German. Code, comments, commits and docs in English.
- Host: Windows 11, Docker Desktop (WSL2), RTX 3090, driver 591.86 (CUDA 13 capable).
  Everything large goes to `data/` (git-ignored) on F:.
- Run pipeline code inside the container: `docker compose up -d --build`, then
  `docker exec cww-trainer py-train ...` (TF/microWakeWord) or `docker exec cww-trainer py-tts ...`
  (Piper/TTS). Always use these launchers: they set LD_LIBRARY_PATH to the venv's CUDA pip libs.
  The two venvs need different CUDA majors (12 vs 13), so never share LD_LIBRARY_PATH.
- From Git Bash, prefix docker commands with `MSYS_NO_PATHCONV=1`, otherwise `/opt/...` paths get
  rewritten to `C:/Program Files/Git/opt/...`.
- GPU code must fail hard when CUDA is unavailable (never silently fall back to CPU).
- Image rebuilds take ~10 min (layer export of ~16 GB). For quick experiments, install extra pinned
  packages into the running container and add them to `docker/requirements-*.in` for the next build.
- Docker Desktop's disk lives on F: (`F:\DockerVolumes\DockerDesktopWSL`, set via `CustomWslDistroDir`
  in `%APPDATA%\Docker\settings-store.json`). The GUI move fails (robocopy exit 1 treated as error).
- Old trainer volume is `wake-word_mww-data` (not `mww-data`); mount it read-only only.
- Dependency policy: exact pins, released >= 7 days ago. Regenerate lock files with
  `uv pip compile ... --exclude-newer <today-7d>` (see README). npm: `npm install --before=<today-7d>`.
- UI: `ui/` (Svelte 5 runes, TypeScript). Verify with `npm run check` and `npm run build` in `ui/`.
  The container serves `ui/dist` plus `/api` on port 8790; `npm run dev` serves on 5173 with a proxy.
  UI strings are English. Look: "Dark Neon / Synth" (tokens in `ui/src/app.css`).
- UI structure is project-first: start page = wake word list, "New wake word" = wizard, project page =
  step bar (`ui/src/lib/steps.ts`: wakeword, generate, record, train, mining, export). New features
  go into their step page under `ui/src/pages/steps/`; set `available: true` in `steps.ts` when a step
  works. Hash routes: `#/`, `#/new`, `#/p/<slug>/<step>`. All per-wake-word data lives in
  `data/projects/<slug>/`; APIs are `/api/projects/...` and `/api/projects/<slug>/studio/...`.
- After a UI build the container picks up `ui/dist` immediately (no restart); uvicorn reloads on `trainer/` changes.
- Quick backend run on the host without Docker (Studio only, no GPU):
  `uv run --no-project --python 3.12 --with fastapi==0.142.4 --with uvicorn==0.54.0 --with soundfile==0.14.0 --with scipy==1.18.1 --with numpy==2.5.3 python -m uvicorn trainer.server.app:app --port 8790`
- Playwright MCP may only write screenshots below `C:\Users\patric` (e.g. `~/.playwright-mcp/`).
- Reference implementation (old trainer): container `mww-trainer`, volume `mww-data`,
  repo `F:\Github\wake-word` (published models in `models/`, Sample Studio in `tools/`).
- Quick local CPU check without Docker:
  `uv run --no-project --python 3.12 --with piper-tts==1.8.0 --with onnx==1.19.1 --with soundfile==0.14.0 --with scipy==1.18.1 --with numpy==2.5.3 python spikes/piper_throughput.py --cpu --count 100`
