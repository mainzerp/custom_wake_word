# Two isolated venvs in one image:
#   /opt/venv-train : TensorFlow 2.21 + microWakeWord (CUDA 12 pip libs)
#   /opt/venv-tts   : Piper + onnxruntime-gpu (CUDA 13 pip libs)
# GPU driver comes from the host (WSL2 /dev/dxg), CUDA runtimes come from pip wheels.
FROM python:3.12.14-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

COPY docker/requirements-train.txt /tmp/requirements-train.txt
RUN uv venv /opt/venv-train --python /usr/local/bin/python3.12 \
    && grep -v '^microwakeword' /tmp/requirements-train.txt > /tmp/requirements-train-deps.txt \
    && uv pip install --python /opt/venv-train/bin/python --no-cache -r /tmp/requirements-train-deps.txt

# microWakeWord's audio/ and layers/ lack __init__.py, so a plain pip install drops them.
ARG MWW_COMMIT=4665173cd35f1cff9a61e06fc427f124766c488e
RUN git clone https://github.com/kahrendt/microWakeWord /opt/microWakeWord \
    && git -C /opt/microWakeWord checkout --quiet "$MWW_COMMIT" \
    && touch /opt/microWakeWord/microwakeword/audio/__init__.py /opt/microWakeWord/microwakeword/layers/__init__.py \
    && uv pip install --python /opt/venv-train/bin/python --no-cache --no-deps /opt/microWakeWord

COPY docker/requirements-tts.txt /tmp/requirements-tts.txt
# piper-tts pulls the CPU onnxruntime, which shadows onnxruntime-gpu (same module name).
RUN uv venv /opt/venv-tts --python /usr/local/bin/python3.12 \
    && uv pip install --python /opt/venv-tts/bin/python --no-cache -r /tmp/requirements-tts.txt \
    && uv pip uninstall --python /opt/venv-tts/bin/python onnxruntime onnxruntime-gpu \
    && uv pip install --python /opt/venv-tts/bin/python --no-cache --no-deps \
       "$(grep -E '^onnxruntime-gpu==' /tmp/requirements-tts.txt)"

# OmniVoice (voice-cloning TTS for synthetic positives) + Whisper filter, PyTorch with CUDA 13 pip libs.
COPY docker/requirements-omni.txt /tmp/requirements-omni.txt
RUN uv venv /opt/venv-omni --python /usr/local/bin/python3.12 \
    && uv pip install --python /opt/venv-omni/bin/python --no-cache -r /tmp/requirements-omni.txt

# Per-venv launchers. TF does not find all CUDA 12 pip libs (e.g. libcusolver) by itself,
# but LD_LIBRARY_PATH must not leak into the TTS venv (both ship libcudnn.so.9).
# onnxruntime-gpu likewise does not find the CUDA 13 pip libs (libcublasLt.so.13).
RUN for v in train tts omni; do \
        printf '#!/bin/sh\nexport LD_LIBRARY_PATH="%s${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\nexec /opt/venv-%s/bin/python "$@"\n' \
            "$(ls -d /opt/venv-$v/lib/python3.12/site-packages/nvidia/*/lib | tr '\n' ':' | sed 's/:$//')" "$v" \
            > /usr/local/bin/py-$v \
        && chmod +x /usr/local/bin/py-$v; \
    done

ENV TF_FORCE_GPU_ALLOW_GROWTH=true \
    TF_GPU_ALLOCATOR=cuda_malloc_async \
    TF_XLA_FLAGS=--tf_xla_auto_jit=0 \
    TF_CPP_MIN_LOG_LEVEL=1

WORKDIR /app
CMD ["sleep", "infinity"]
