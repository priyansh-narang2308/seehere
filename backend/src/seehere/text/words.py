"""Matching what is shown with what is said: distinctive words and spoken numbers."""

from __future__ import annotations

import re
from decimal import Decimal

from seehere.text.numbers import extract_numbers, words_to_number

MAX_NUMBER_WORDS = 8
# "three point two million": words_to_number stops at the decimal, so apply the scale here
_SCALE_WORDS = {"thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12}

_WORD = re.compile(r"[a-z]+")
_STOP_WORDS = (
    "the and for are but not you all any can had her was one our out has have this that with "
    "from they will would there their what which when your into than then them these those "
    "its also been more most some such only over very just about"
)
_STOP = frozenset(_STOP_WORDS.split())


def stem(word: str) -> str:
    """Fold common English plurals: categories -> category, boxes -> box, lines -> line."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and word[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def content_words(text: str) -> set[str]:
    """Distinctive words: 3+ letters, not a stop word, plural folded."""
    return {stem(w) for w in _WORD.findall(text.lower()) if len(w) >= 3 and w not in _STOP}


_SPLIT_NUMBER = re.compile(r"(\d) (?=[.,]\d|%)")


def join_words(words: list[str]) -> str:
    """Transcript words to text. Speech-to-text may split one number across words
    ("12", ".5%"), so those pieces are joined back together."""
    return _SPLIT_NUMBER.sub(r"\1", " ".join(words))


def spoken_numbers(text: str) -> list[Decimal]:
    """Values said as digits ("12.5") or as words ("twelve point five")."""
    values = [m.value for m in extract_numbers(text)]
    words = _WORD.findall(text.lower())
    i = 0
    while i < len(words):
        # the longest run of words starting here that reads as one number
        for j in range(min(len(words), i + MAX_NUMBER_WORDS), i, -1):
            value = words_to_number(" ".join(words[i:j]))
            if value is not None:
                if j < len(words) and words[j] in _SCALE_WORDS:
                    value *= _SCALE_WORDS[words[j]]
                    j += 1
                values.append(value)
                i = j
                break
        else:
            i += 1
    return values
