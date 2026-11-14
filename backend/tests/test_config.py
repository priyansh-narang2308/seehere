"""Settings parsing."""

from __future__ import annotations

from seehere.core.config import Settings


def test_a_blank_api_key_means_not_configured() -> None:
    assert Settings(vultr_inference_api_key="").vultr_inference_api_key is None
    assert Settings(vultr_inference_api_key="  ").vultr_inference_api_key is None
    key = Settings(vultr_inference_api_key=" abc \n").vultr_inference_api_key
    assert key is not None and key.get_secret_value() == "abc"
