"""Number normalization, so numbers read from the screen (OCR) and heard in speech (STT) can
be compared later (seen-versus-said, claim verification).

- `extract_numbers("Revenue rose 12.5% to $3.2M")` finds 12.5 (percent) and 3200000 (USD).
- `words_to_number("two point five million")` gives 2500000.
- `fix_ocr_digits("1O0")` repairs common OCR letter/digit confusions inside numeric tokens.
- `same_number(a, b)` compares two values, allowing for the rounding shown on a slide.

Values are `Decimal`, so 0.1 + 0.2 style float errors never decide a comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_SCALES = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "m": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "b": Decimal(1_000_000_000),
    "bn": Decimal(1_000_000_000),
    "billion": Decimal(1_000_000_000),
    "trillion": Decimal(1_000_000_000_000),
}
_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}

# A number: optional sign/currency, digits with thousands separators or plain, decimals, then an
# optional scale word/suffix and percent sign.
_NUMBER = re.compile(
    r"(?<![\w.])"
    r"(?P<sign>[-−–]?)"
    r"(?P<cur>[$€£¥₹]?)"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
    r"(?!\d|\.\d)"  # not part of a longer token such as a version "3.12.1"
    r"(?:\s?(?P<scale>thousand|million|billion|trillion|bn|mn|[kKmMbB])(?![\w]))?"
    r"(?P<pct>\s?(?:%|percent\b|per cent\b))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NumberMention:
    value: Decimal
    raw: str
    start: int
    end: int
    percent: bool = False
    currency: str | None = None
    decimals: int = 0  # digits after the point as written: tells how much it was rounded
    scale: Decimal = Decimal(1)  # multiplier of a suffix such as "k" or "million"


def extract_numbers(text: str) -> list[NumberMention]:
    out = []
    for m in _NUMBER.finditer(text):
        digits = m["num"].replace(",", "")
        try:
            value = Decimal(digits)
        except InvalidOperation:  # pragma: no cover - the pattern only matches valid numbers
            continue
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        scale = _SCALES[m["scale"].lower()] if m["scale"] else Decimal(1)
        value *= scale
        if m["sign"]:
            value = -value
        out.append(
            NumberMention(
                value=value,
                raw=m.group(0).strip(),
                start=m.start(),
                end=m.end(),
                percent=bool(m["pct"]),
                currency=_CURRENCY.get(m["cur"]) if m["cur"] else None,
                decimals=decimals,
                scale=scale,
            )
        )
    return out


_UNITS = {
    w: i
    for i, w in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
    )
}
_TENS = {
    w: 10 * i
    for i, w in enumerate(
        ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    )
    if w != "_"
}
_BIG = {"thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12}


def words_to_number(text: str) -> Decimal | None:
    """English number words to a value: "three hundred and twelve" -> 312,
    "minus four point two five" -> -4.25. Returns None if the text is not only a number."""
    tokens = re.findall(r"[a-z]+", text.lower().replace("-", " "))
    if not tokens:
        return None
    negative = tokens[0] in ("minus", "negative")
    if negative:
        tokens = tokens[1:]
    total = current = 0
    fraction: list[int] | None = None
    seen = False
    for t in tokens:
        if fraction is not None:
            if t not in _UNITS or _UNITS[t] > 9:
                return None
            fraction.append(_UNITS[t])
        elif t in _UNITS:
            current += _UNITS[t]
            seen = True
        elif t in _TENS:
            current += _TENS[t]
            seen = True
        elif t == "hundred" and seen:
            current = max(current, 1) * 100
        elif t in _BIG and seen:
            total += max(current, 1) * _BIG[t]
            current = 0
        elif t == "and" and seen:
            continue
        elif t == "point" and seen:
            fraction = []
        else:
            return None
    if not seen or fraction == []:
        return None
    value = Decimal(total + current)
    if fraction:
        value += Decimal("0." + "".join(map(str, fraction)))
    return -value if negative else value


_OCR_CONFUSIONS = str.maketrans(
    {"O": "0", "o": "0", "D": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"}
)
_NUMERIC_TOKEN = re.compile(r"(?<![A-Za-z])[0-9OoDlI|SB.,]*\d[0-9OoDlI|SB.,]*(?![A-Za-z])")


def fix_ocr_digits(text: str) -> str:
    """Repair letters OCR often reads in place of digits, only inside tokens that already
    contain a digit and no other letters ("1O0" -> "100", "2l.5" -> "21.5"; "Oslo" untouched)."""
    return _NUMERIC_TOKEN.sub(lambda m: m.group(0).translate(_OCR_CONFUSIONS), text)


def same_number(shown: NumberMention, said: Decimal, *, allow_fraction: bool = True) -> bool:
    """Whether a spoken value agrees with a number shown on screen, allowing for the rounding
    the slide used: "12.5%" agrees with 12.5, and "3.2M" with 3,180,000 (which rounds to 3.2M).
    A percentage also matches its fraction (12.5% and 0.125) unless `allow_fraction` is False."""
    candidates = [said, said * 100] if shown.percent and allow_fraction else [said]
    # Half a unit of the last digit as written, in the written scale.
    tolerance = shown.scale * Decimal(5) / Decimal(10) ** (shown.decimals + 1)
    return any(abs(c - shown.value) <= tolerance for c in candidates)
