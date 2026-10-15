"""Multi-speaker Piper voices per language (pure data, importable from both venvs)."""

from __future__ import annotations

VOICE_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# language -> (voice name, path below VOICE_BASE_URL, speakers)
VOICES: dict[str, tuple[str, str, int]] = {
    "de": ("de_DE-mls-medium", "de/de_DE/mls/medium", 236),
    "en": ("en_US-libritts_r-medium", "en/en_US/libritts_r/medium", 904),
    "fr": ("fr_FR-mls-medium", "fr/fr_FR/mls/medium", 125),
    "nl": ("nl_NL-mls-medium", "nl/nl_NL/mls/medium", 52),
}


def voice_for(language: str) -> dict | None:
    if language not in VOICES:
        return None
    name, path, speakers = VOICES[language]
    return {"name": name, "url": f"{VOICE_BASE_URL}/{path}/{name}", "speakers": speakers}
