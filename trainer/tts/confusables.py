"""Sound-alike negatives ("confusables"): words that sound close to the wake word but are clearly not it.

They are the false triggers a model learns least from generic speech, so the "Synthetic samples" step speaks them
with the same voice bank (trainer.tts.omni, mode "confusable"). Suggestions come from two sources:

  edits   letter edits of the spellings: other onset ("Garvis", "Arvis"), other vowel ("Jervis"), other or dropped
          inner consonant ("Jarbis", "Jaris"), a few endings ("Jarviser")
  words   real words and word pairs from the voice bank transcripts ("Paris", "schau mal") - natural for the TTS and
          the kind of thing that triggers a model in a real living room

Every candidate is scored with the espeak phone distance to the closest spelling (trainer.tts.phonetic). Only the
band CONFLICT_MAX < distance <= MAX_DISTANCE is kept: closer would be the wake word itself (contradicting labels),
farther is ordinary speech the generic negatives cover anyway.
"""

from __future__ import annotations

import re
from functools import lru_cache

from trainer.tts import phonetic
from trainer.tts.voices import load_bank

MAX_DISTANCE = 0.65
MAX_WORDS = 6000

DIPHTHONGS = ["ei", "ey", "ie", "au", "eu", "äu", "ai", "ay", "ee", "oo", "ou", "oy"]
MULTI = ["tsch", "dsch", "sch", "ch", "ck", "ph", "th", "qu", *DIPHTHONGS]
VOWEL_UNITS = set("aeiouyäöü") | set(DIPHTHONGS)
ONSETS = {
    "de": ["", "b", "d", "g", "k", "m", "n", "p", "t", "w", "l", "r", "s", "h", "f", "z", "sch", "ch", "j", "tsch",
           "kl", "st"],
    "en": ["", "b", "d", "g", "k", "m", "n", "p", "t", "w", "l", "r", "s", "h", "f", "j", "ch", "sh", "y",
           "cl", "st"],
}
CONSONANTS = {
    "de": ["b", "d", "g", "k", "l", "m", "n", "p", "r", "s", "t", "w", "f", "z", "ch", "sch"],
    "en": ["b", "d", "g", "k", "l", "m", "n", "p", "r", "s", "t", "w", "f", "v", "z", "sh"],
}
VOWELS = {
    "de": ["a", "e", "i", "o", "u", "ä", "ö", "ü", "ei", "au"],
    "en": ["a", "e", "i", "o", "u", "ee", "oo", "ay", "ow"],
}
ENDINGS = {"de": ["er", "en", "a", "o", "t"], "en": ["er", "en", "a", "o", "y"]}
WORD_RE = re.compile(r"[^\W\d_]{3,}")
PHONE_VOWELS = set("aeiouyæɑɐɒɔəɛɜɪʊʌʏøœɯɨʉɵɤ")


def units(word: str) -> list[str]:
    out, i = [], 0
    while i < len(word):
        for m in MULTI:
            if word.startswith(m, i):
                out.append(m)
                i += len(m)
                break
        else:
            out.append(word[i])
            i += 1
    return out


def is_vowel(u: str) -> bool:
    return u in VOWEL_UNITS


def edits(spelling: str, language: str) -> dict[str, str]:
    """Letter edits of every word of the spelling -> kind of edit (onset, vowel, inner, ending)."""
    lang = language if language in ONSETS else "en"
    words = spelling.lower().split()
    out: dict[str, str] = {}
    for wi, word in enumerate(words):
        us = units(word)
        first_vowel = next((i for i, u in enumerate(us) if is_vowel(u)), len(us))
        variants: dict[str, str] = {}
        rest = us[first_vowel:]
        for onset in ONSETS[lang]:
            variants.setdefault(onset + "".join(rest), "onset")
            for v in VOWELS[lang] if rest else []:
                variants.setdefault(onset + v + "".join(rest[1:]), "onset")
        for i in range(first_vowel, len(us)):
            vowel = is_vowel(us[i])
            for rep in VOWELS[lang] if vowel else CONSONANTS[lang] + [""]:
                variants.setdefault("".join(us[:i] + [rep] + us[i + 1:]), "vowel" if vowel else "inner")
        for end in ENDINGS[lang]:
            variants.setdefault(word + end, "ending")
        for v, kind in variants.items():
            if v != word and any(is_vowel(u) for u in units(v)):
                text = " ".join(words[:wi] + [v] + words[wi + 1:])
                out.setdefault(text[:1].upper() + text[1:], kind)
    return out


def bank_words(language: str) -> set[str]:
    """Words and adjacent word pairs from the reference transcripts of the voice bank."""
    out: set[str] = set()
    for v in load_bank(language):
        tokens = WORD_RE.findall(v.get("text", ""))
        out.update(tokens)
        out.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))
        if len(out) >= MAX_WORDS:
            break
    return out


def closeness(cand: tuple[str, ...], target: tuple[str, ...]) -> float:
    """Distance as the clip check sees it (normalized by the wake word); 0 when the wake word sits inside the
    candidate ("Hey Jarvis", "Jarvisse"), which would make its clips contradict the positives."""
    c, t = list(cand), list(target)
    if phonetic.contained_distance(c, t) <= phonetic.POSITIVE_MAX:
        return 0.0
    return phonetic.distance(c, t)


def score(texts: list[str], spellings: list[str], language: str) -> list[float]:
    targets = phonetic.phrases_phones(spellings, language)
    phones = phonetic.phrases_phones(texts, language)
    return [round(min(closeness(p, t) for t in targets), 3) if p else 1.0 for p in phones]


def similar_length(phones: tuple[str, ...], targets: list[tuple[str, ...]]) -> bool:
    return any(0.6 * len(t) <= len(phones) <= 1.6 * len(t) for t in targets)


def level(d: float) -> str:
    return "conflict" if d <= phonetic.CONFLICT_MAX else "ok" if d <= MAX_DISTANCE else "far"


def skeleton(phones: tuple[str, ...]) -> tuple[str, ...]:
    """Consonant frame of a word: "Stervis", "Storvis" and "Störvis" share one, so only one of them is suggested."""
    return tuple(p for p in phones if not set(p) & PHONE_VOWELS)


@lru_cache(maxsize=32)
def ranked(spellings: tuple[str, ...], language: str) -> dict[str, list[tuple[str, float]]]:
    """All candidates in the useful band per kind, closest first."""
    pools: dict[str, str] = {w: "word" for w in bank_words(language)}
    for s in spellings:
        pools.update(edits(s, language))
    targets = phonetic.phrases_phones(list(spellings), language)
    texts = sorted(t for t in pools if t.lower() not in {s.lower() for s in spellings})
    texts = [t for t, p in zip(texts, phonetic.phrases_phones(texts, language)) if similar_length(p, targets)]
    out: dict[str, list[tuple[str, float]]] = {}
    for t, d in zip(texts, score(texts, list(spellings), language)):
        if phonetic.CONFLICT_MAX < d <= MAX_DISTANCE:
            out.setdefault(pools[t], []).append((t, d))
    return {k: sorted(v, key=lambda x: (x[1], len(x[0]))) for k, v in out.items()}


def suggest(spellings: list[str], language: str, n: int = 24, exclude: list[str] = ()) -> list[dict]:
    """n diverse sound-alikes, taken round-robin from real words and each kind of letter edit, closest first."""
    pools = {k: list(v) for k, v in ranked(tuple(spellings), language).items()}
    taken = {e.lower() for e in exclude}
    seen = {skeleton(p) for p in phonetic.phrases_phones(list(exclude) + list(spellings), language)}
    order = [k for k in ("word", "onset", "inner", "vowel", "ending") if k in pools]
    out: list[dict] = []
    while len(out) < n and any(pools[k] for k in order):
        for kind in order:
            while pools[kind] and len(out) < n:
                text, d = pools[kind].pop(0)
                frame = skeleton(phonetic.phrase_phones(text, language))
                if text.lower() not in taken and frame not in seen:
                    seen.add(frame)
                    out.append({"text": text, "distance": d, "kind": kind})
                    break
    return sorted(out, key=lambda x: x["distance"])
