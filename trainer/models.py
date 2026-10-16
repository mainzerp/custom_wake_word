"""Hugging Face models the pipeline loads, pinned to exact revisions (dependency policy: exact pins).

The setup (trainer/setup.py) prefetches them into HF_HOME; the loaders pass the same revision, so a fresh machine
gets exactly these weights and a later upstream commit changes nothing until it is pinned here.
"""

OMNIVOICE = ("k2-fsa/OmniVoice", "c5fdb5ccb189668d56333f77ba2629f4cd7535f4")  # TTS, 3.3 GB, CC-BY-NC 4.0 weights
PHONES = ("facebook/wav2vec2-xlsr-53-espeak-cv-ft", "2c733782da5604684829819a5eb744c193fe9398")  # IPA phones, 1.3 GB
WHISPER = ("openai/whisper-large-v3-turbo", "41f01f3fe87f28c78e2fbf8b568835947dd65ed9")  # transcripts, 1.6 GB

ALL = {"omnivoice": OMNIVOICE, "phones": PHONES, "whisper": WHISPER}


def local(model: tuple[str, str]) -> str:
    """Local snapshot directory of a pinned model, downloaded into HF_HOME on first use (OmniVoice venv)."""
    from huggingface_hub import snapshot_download

    repo, revision = model
    return snapshot_download(repo, revision=revision)
