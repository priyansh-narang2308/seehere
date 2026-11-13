"""Exceptions that handlers raise to tell the worker how a job ended."""

from __future__ import annotations


class JobCancelled(Exception):
    """The job was cancelled (by request, or because this worker lost its lease)."""


class PermanentJobError(Exception):
    """A failure that retrying cannot fix, such as a corrupt input file.

    `message` is shown to users, so it must not contain paths, stack traces or secrets.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RetryableJobError(Exception):
    """A failure that may go away on a later attempt (a model download that timed out, a
    provider that is briefly unavailable). Retried with backoff like an unexpected error, but
    `message` is shown to users instead of the generic text, so it must be safe to show.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
