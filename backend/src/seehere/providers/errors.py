"""Hosted-provider failures, classified so a job knows whether retrying can help.

A provider error carries the HTTP status when there was one. 429, 408 and 5xx replies and
network failures may pass, so they are retried; a rejected key (401/403) or a refused request
(other 4xx) will fail the same way every time, so the job stops with a message saying what to
fix. Messages never contain the API key.
"""

from __future__ import annotations

from seehere.jobs.errors import PermanentJobError, RetryableJobError

TRANSIENT_STATUS = {408, 429}


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, *, status: int | None = None, retryable: bool | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = (
            retryable
            if retryable is not None
            else status is None or status in TRANSIENT_STATUS or status >= 500
        )


def job_error(exc: ProviderError, service: str) -> PermanentJobError | RetryableJobError:
    """The job outcome for a provider failure, with a message safe to show users."""
    if exc.status in (401, 403):
        return PermanentJobError(
            f"{service} rejected the API key (HTTP {exc.status}). Check VULTR_INFERENCE_API_KEY "
            "and that the Serverless Inference subscription is active, then retry."
        )
    if exc.retryable:
        detail = f"HTTP {exc.status}" if exc.status else "no response"
        return RetryableJobError(f"{service} is unavailable right now ({detail}).")
    detail = f" (HTTP {exc.status})" if exc.status else ""
    return PermanentJobError(f"{service} refused the request{detail}: {exc}.")
