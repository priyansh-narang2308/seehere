"""Claim verification: each claim is checked against the cue's own evidence, and the cue takes
the weakest result."""

from __future__ import annotations

from seehere.db.enums import CheckResult, VerificationState
from seehere.describe.verify import OcrLine, Sources, verify_texts

V = VerificationState
OCR = Sources(ocr=[OcrLine("Revenue rose 12.5% to $3.2M", 0.93)])


def _verify(
    texts: list[str], src: Sources
) -> tuple[VerificationState, list[tuple[str, str, CheckResult]]]:
    state, checks = verify_texts(texts, src)
    return state, [(c.name, c.claim, c.result) for c in checks]


def test_quote_and_numbers_read_on_screen_are_a_verified_text_match() -> None:
    state, checks = _verify(["On screen: “Revenue rose 12.5% to $3.2M”."], OCR)
    assert state is V.VERIFIED_TEXT_MATCH
    assert checks == [
        ("quote_match", "Revenue rose 12.5% to $3.2M", CheckResult.PASS),
        ("number_match", "12.5%", CheckResult.PASS),
        ("number_match", "$3.2M", CheckResult.PASS),
    ]


def test_a_number_not_on_screen_downgrades_the_cue() -> None:
    state, checks = _verify(["On screen: “Revenue rose 15% to $3.2M”."], OCR)
    assert state is V.NEEDS_REVIEW
    assert ("number_match", "15%", CheckResult.FAIL) in checks
    assert ("quote_match", "Revenue rose 15% to $3.2M", CheckResult.FAIL) in checks
    # 12.5 is not 12.5%: the unit is part of the value
    assert _verify(["Revenue rose 12.5"], OCR)[0] is V.NEEDS_REVIEW


def test_weak_text_evidence_is_uncertain() -> None:
    low = Sources(ocr=[OcrLine("Revenue rose 12.5% to $3.2M", 0.41)])
    assert _verify(["On screen: “Revenue rose 12.5% to $3.2M”."], low)[0] is V.UNCERTAIN
    misread = Sources(ocr=[OcrLine("Total 1O0 units", 0.95)])  # OCR read a letter O
    state, checks = _verify(["Table: Totals. 100."], Sources(ocr=misread.ocr, seen_by_model=True))
    assert state is V.UNCERTAIN
    assert ("number_match", "100", CheckResult.INCONCLUSIVE) in checks


def test_deck_text_verifies_and_quotes_must_be_more_than_a_fragment() -> None:
    deck = Sources(slides=["Next steps\nHire 3 engineers by March"])
    assert _verify(["On screen: “Hire 3 engineers by March”."], deck)[0] is V.VERIFIED_TEXT_MATCH
    tiny = Sources(ocr=[OcrLine("Revenue rose 12.5% to $3.2M in the third quarter", 0.95)])
    assert _verify(["On screen: “rose”."], tiny)[0] is V.NEEDS_REVIEW
    cut = Sources(ocr=[OcrLine(" ".join(f"w{i}" for i in range(30)), 0.95)])
    quote = " ".join(f"w{i}" for i in range(15)) + "…"
    assert _verify([f"On screen: “{quote}”."], cut)[0] is V.VERIFIED_TEXT_MATCH


def test_descriptions_need_a_vision_model_and_are_only_corroborated() -> None:
    texts = [
        "Chart: Bar chart of revenue by quarter.",
        "Chart: Bar chart of revenue. Four bars rise.",
    ]
    seen = Sources(ocr=OCR.ocr, seen_by_model=True)
    state, checks = _verify(texts, seen)
    assert state is V.CORROBORATED
    assert [c for c in checks if c[0] == "description_support"] == [
        ("description_support", "Bar chart of revenue by quarter", CheckResult.INCONCLUSIVE),
        ("description_support", "Bar chart of revenue", CheckResult.INCONCLUSIVE),
        ("description_support", "Four bars rise", CheckResult.INCONCLUSIVE),
    ]
    # The same statement with only OCR behind it: nothing supports it.
    assert _verify(texts, OCR)[0] is V.NEEDS_REVIEW
    assert _verify([], OCR)[0] is V.NEEDS_REVIEW
