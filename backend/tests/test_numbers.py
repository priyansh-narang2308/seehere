from __future__ import annotations

from decimal import Decimal

import pytest

from seehere.text.numbers import extract_numbers, fix_ocr_digits, same_number, words_to_number


@pytest.mark.parametrize(
    ("text", "value", "percent", "currency"),
    [
        ("12", "12", False, None),
        ("1,234,567", "1234567", False, None),
        ("3.14", "3.14", False, None),
        (".5", "0.5", False, None),
        ("12.5%", "12.5", True, None),
        ("40 percent", "40", True, None),
        ("$3.2M", "3200000", False, "USD"),
        ("€1.5 billion", "1500000000", False, "EUR"),
        ("2.5k", "2500", False, None),
        ("−4.2", "-4.2", False, None),  # Unicode minus, as slides often use
        ("-7%", "-7", True, None),
    ],
)
def test_extracts_one_number(text: str, value: str, percent: bool, currency: str | None) -> None:
    [n] = extract_numbers(text)
    assert (n.value, n.percent, n.currency) == (Decimal(value), percent, currency)


def test_extracts_several_with_positions() -> None:
    text = "Sales rose 12.5% in 2022 to $3.2M (from 2,840,000)."
    found = extract_numbers(text)
    assert [n.value for n in found] == [
        Decimal("12.5"),
        Decimal(2022),
        Decimal(3200000),
        Decimal(2840000),
    ]
    assert [text[n.start : n.end].strip() for n in found] == [n.raw for n in found]


def test_ignores_digits_inside_words_and_versions() -> None:
    assert extract_numbers("COVID19 and v2 and H2O") == []
    assert extract_numbers("Python 3.12.1 on 192.168.0.1") == []
    assert extract_numbers("no numbers here") == []


@pytest.mark.parametrize(
    ("words", "value"),
    [
        ("zero", "0"),
        ("seven", "7"),
        ("twenty three", "23"),
        ("twenty-three", "23"),
        ("three hundred and twelve", "312"),
        ("two thousand twenty two", "2022"),
        ("two point five million", None),  # "million" after a fraction is not supported
        ("one million two hundred thousand", "1200000"),
        ("four point two five", "4.25"),
        ("minus forty", "-40"),
    ],
)
def test_words_to_number(words: str, value: str | None) -> None:
    assert words_to_number(words) == (Decimal(value) if value else None)


@pytest.mark.parametrize("words", ["", "hundred", "the chart", "five apples", "point five"])
def test_words_that_are_not_a_number(words: str) -> None:
    assert words_to_number(words) is None


@pytest.mark.parametrize(
    ("ocr", "fixed"),
    [
        ("1O0", "100"),
        ("2l.5%", "21.5%"),
        ("revenue 1,2O0", "revenue 1,200"),
        ("Oslo", "Oslo"),  # no digit: left alone
        ("COVID-19", "COVID-19"),
        ("I have 3 cats", "I have 3 cats"),
    ],
)
def test_fix_ocr_digits(ocr: str, fixed: str) -> None:
    assert fix_ocr_digits(ocr) == fixed


def test_same_number_allows_the_rounding_shown() -> None:
    [m] = extract_numbers("$3.2M")
    assert same_number(m, Decimal(3_180_000))  # rounds to 3.2M
    assert same_number(m, Decimal(3_249_999))
    assert not same_number(m, Decimal(3_260_000))
    [p] = extract_numbers("12.5%")
    assert same_number(p, Decimal("12.5"))
    assert same_number(p, Decimal("0.125"))
    assert not same_number(p, Decimal("0.125"), allow_fraction=False)
    assert not same_number(p, Decimal(13))
    [y] = extract_numbers("2022")
    assert same_number(y, Decimal(2022)) and not same_number(y, Decimal(2023))
