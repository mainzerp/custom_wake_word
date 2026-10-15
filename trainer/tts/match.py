"""Does an ASR transcript contain the wake word? Pure Python, shared by the generator filter and spikes.

ASR writes unknown names in many ways ("Jarvis", "Dscharwis", "Tschau bis", "Chavis"), so besides a plain
text match the transcript is compared phonetically (Kölner Phonetik, b/p folded into w/f) with a tolerance of one
edit for longer codes.
"""

from __future__ import annotations

import re

UMLAUTS = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "s"})


def normalize(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower().translate(UMLAUTS))


def koelner(text: str) -> str:
    s = normalize(text)
    codes = []
    for i, c in enumerate(s):
        # "#" as a sentinel: an empty string would count as contained in every rule string.
        prev, nxt = (s[i - 1] if i else "#"), (s[i + 1] if i + 1 < len(s) else "#")
        if i == 0 and (c == "j" or (c == "c" and nxt == "h")):
            code = "8"  # name onsets: ASR writes "dsch" as J or Ch (Jarvis, Chavis, Chavez)
        elif c in "aeijouy":
            code = "0"
        elif c == "h":
            code = ""
        elif c in "bfvw" or c == "p":
            code = "3"  # b/p folded into f/v/w: ASR confuses "Jarvis" with "Ja bis"
        elif c in "dt":
            code = "8" if nxt in "csz" else "2"
        elif c in "gkq":
            code = "4"
        elif c == "c":
            if i == 0:
                code = "4" if nxt in "ahkloqrux" else "8"
            else:
                code = "8" if prev in "sz" or nxt not in "ahkoqux" else "4"
        elif c == "x":
            code = "8" if prev in "ckq" else "48"
        elif c == "l":
            code = "5"
        elif c in "mn":
            code = "6"
        elif c == "r":
            code = "7"
        elif c in "sz":
            code = "8"
        else:
            code = ""
        codes.append(code)
    out: list[str] = []
    for code in "".join(codes):
        if not out or out[-1] != code:
            out.append(code)
    return "".join(c for c in out if c != "0")


def _within_one(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(a) == len(b):
            i += 1
        j += 1
    return edits + (len(b) - j) + (len(a) - i) <= 1


def phonetic_variants(phrases: list[str]) -> list[str]:
    """Codes of the phrases, also with every r (7) dropped: German speakers vocalize it."""
    codes = {koelner(p) for p in phrases}
    return sorted(c for c in codes | {c.replace("7", "") for c in codes} if len(c) >= 3)


def contains_wake_word(transcript: str, phrases: list[str]) -> bool:
    """True if the transcript is (essentially) only the wake word: extra words mean the clip contains other speech."""
    text = normalize(transcript)
    if not text:
        return False
    if any(normalize(p) in text and len(text) <= len(normalize(p)) + 2 for p in phrases):
        return True
    code = koelner(transcript)
    return any(code == target or (len(target) >= 4 and _within_one(code, target)) for target in phonetic_variants(phrases))
