"""Phonetic check of synthetic clips: recognized IPA phones vs. the espeak-ng pronunciation of the spellings.

A multilingual wav2vec2 phone recognizer (facebook/wav2vec2-xlsr-53-espeak-cv-ft) transcribes each clip into IPA
phones; the distance to the closest spelling is a phone-level edit distance where similar phones (r variants, vowels
of one class, voiced/voiceless pairs, ...) cost less, normalized by the target length.

  distance <= POSITIVE_MAX            -> positive (keeps the clip)
  POSITIVE_MAX < distance < NEGATIVE_MIN -> gray (dropped: neither a clean positive nor a safe negative)
  distance >= NEGATIVE_MIN            -> negative candidate (sounds clearly different, e.g. TTS slips like "Davis"),
                                         unless the wake word is contained in the clip (then gray)

Runs in the OmniVoice venv (torch); the target pronunciation needs the espeak-ng binary.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import numpy as np

MODEL = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
# Calibrated with spikes/phonetic_check.py ("Jarvis"/"Dscharwis"): OmniVoice clips 79 % positive / 0 % negative,
# own recordings median 0.24, random 0.6-1.3 s German speech 0 % positive / 88 % negative, Piper MLS gibberish
# 0 % positive; "Garvis" (0.33) and "Davis" (0.44) land in the gray zone.
POSITIVE_MAX = 0.30
NEGATIVE_MIN = 0.70
CONTAINED_MIN = 0.50  # a negative must not contain the wake word inside longer speech either
ONSET_WEIGHT = 2.5
MIN_NEGATIVE_PHONES = 3
RATE = 16000

# Phones that are acoustically close and get confused by both TTS and recognizer: substitution costs 0.4.
SIMILAR = [
    set("rɾʁʀɹɐ") | {"ɐ̯", "r̩"},
    set("aɑɐæʌ"),
    set("eɛəɜ") | {"eː", "ɛː"},
    set("iɪyʏj") | {"iː", "yː"},
    set("oɔ") | {"oː"},
    set("uʊ") | {"uː"},
    set("vwfʋβ"),
    set("bp"),
    set("dt"),
    set("gkɡ"),
    set("szʃʒɕʑ") | {"tʃ", "dʒ", "ts"},
    {"j", "dʒ", "ʒ", "tʃ"},  # "Jarvis": German j vs. English dsch onset
    set("çxχh"),
]
R_SOUNDS = SIMILAR[0]
# Multi-character inventory entries that are single sounds; everything else is split into single phones.
UNITS = {"tʃ", "dʒ", "ts", "pf", "aɪ", "aʊ", "ɔʏ", "ɔɪ", "eɪ", "oʊ"}
STRIP = str.maketrans("", "", "ˈˌ‍͡.0123456789")


def espeak_ipa(text: str, language: str) -> str:
    out = subprocess.run(["espeak-ng", "-q", "--ipa=3", "-v", language, text], capture_output=True, text=True, check=True)
    return out.stdout.strip().translate(STRIP)


def clean(phone: str) -> str:
    return phone.translate(STRIP)


def tokenize(ipa: str, vocab: set[str]) -> list[str]:
    """Greedy longest match of an espeak IPA string onto single phones of the recognizer's inventory."""
    ipa = ipa.replace(" ", "").replace("_", "")
    vocab = {v for v in vocab if len(v) == 1 or v in UNITS or (len(v) == 2 and v.endswith("ː"))}
    longest = max(len(v) for v in vocab)
    out, i = [], 0
    while i < len(ipa):
        for n in range(min(longest, len(ipa) - i), 0, -1):
            if ipa[i:i + n] in vocab:
                out.append(ipa[i:i + n])
                i += n
                break
        else:
            i += 1  # stress marks, unknown diacritics
    return out


def _base(p: str) -> str:
    return p.replace("ː", "")


def sub_cost(a: str, b: str) -> float:
    if a == b or _base(a) == _base(b):
        return 0.0
    return 0.4 if any(a in g and b in g or _base(a) in g and _base(b) in g for g in SIMILAR) else 1.0


def indel_cost(p: str) -> float:
    return 0.4 if p in R_SOUNDS else 1.0  # German speakers vocalize or drop the r ("Dschawis")


def weights(target: list[str]) -> list[float]:
    """The onset carries the word's identity ("Davis", "Garvis" vs. "Dscharwis"), so it counts twice."""
    return [ONSET_WEIGHT] + [1.0] * (len(target) - 1)


def distance(phones: list[str], target: list[str]) -> float:
    """Weighted edit distance normalized by the target weight (0 = identical, 1 = everything differs)."""
    if not target:
        return 1.0
    w = weights(target)
    prev = [0.0]
    for b, wb in zip(target, w):
        prev.append(prev[-1] + wb * indel_cost(b))
    for a in phones:
        cur = [prev[0] + indel_cost(a)]
        for j, (b, wb) in enumerate(zip(target, w), 1):
            cur.append(min(prev[j] + indel_cost(a), cur[j - 1] + wb * indel_cost(b), prev[j - 1] + wb * sub_cost(a, b)))
        prev = cur
    return prev[-1] / sum(w)


def contained_distance(phones: list[str], target: list[str]) -> float:
    """Like distance(), but extra phones before/after the target are free: does the clip contain the wake word?"""
    if not target:
        return 1.0
    w = weights(target)
    prev = [0.0] * (len(phones) + 1)
    for b, wb in zip(target, w):
        cur = [prev[0] + wb * indel_cost(b)]
        for i, a in enumerate(phones, 1):
            cur.append(min(prev[i] + wb * indel_cost(b), cur[i - 1] + indel_cost(a), prev[i - 1] + wb * sub_cost(a, b)))
        prev = cur
    return min(prev) / sum(w)


@dataclass
class Score:
    phones: list[str]
    distance: float
    band: str  # positive | gray | negative


def band(full: float, contained: float, n_phones: int) -> str:
    if full <= POSITIVE_MAX:
        return "positive"
    # A clip that contains the wake word plus other speech ("Blad-scharwis") must never become a negative, and
    # clips with hardly any recognized phones are hum or noise from a failed generation, not speech.
    return "negative" if full >= NEGATIVE_MIN and contained >= CONTAINED_MIN and n_phones >= MIN_NEGATIVE_PHONES else "gray"


class PhoneChecker:
    def __init__(self, language: str, phrases: list[str], device: str = "cuda"):
        import torch
        from huggingface_hub import hf_hub_download
        from transformers import AutoModelForCTC, Wav2Vec2FeatureExtractor

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA not available; refusing to run the phone recognizer on the CPU")
        self.torch, self.device = torch, device
        vocab = json.loads(open(hf_hub_download(MODEL, "vocab.json"), encoding="utf-8").read())
        self.id2tok = {i: t for t, i in vocab.items()}
        self.special = {t for t in vocab if t.startswith("<") or t in ("|", "")}
        self.extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL)
        self.model = AutoModelForCTC.from_pretrained(MODEL, dtype=torch.float16).to(device).eval()
        inventory = {t for t in vocab if t not in self.special}
        self.targets = {p: tokenize(espeak_ipa(p, language), inventory) for p in phrases}

    def transcribe(self, clips: list[np.ndarray]) -> list[list[str]]:
        if not clips:
            return []
        inp = self.extractor(clips, sampling_rate=RATE, return_tensors="pt", padding=True, return_attention_mask=True)
        with self.torch.inference_mode():
            logits = self.model(inp.input_values.to(self.device, self.torch.float16),
                                attention_mask=inp.attention_mask.to(self.device)).logits
        ids = logits.argmax(-1).cpu().numpy()
        frames = (inp.attention_mask.sum(1).numpy() / RATE * 50).astype(int) + 1  # 20 ms frames
        out = []
        for row, n in zip(ids, frames):
            phones, last = [], None
            for i in row[:n]:
                tok = self.id2tok.get(int(i), "")
                if tok != last and tok not in self.special and clean(tok):
                    phones.append(clean(tok))
                last = tok
            out.append(phones)
        return out

    def score(self, clips: list[np.ndarray]) -> list[Score]:
        result = []
        for phones in self.transcribe(clips):
            d = min(distance(phones, t) for t in self.targets.values())
            c = min(contained_distance(phones, t) for t in self.targets.values())
            result.append(Score(phones, round(d, 3), band(d, c, len(phones))))
        return result
