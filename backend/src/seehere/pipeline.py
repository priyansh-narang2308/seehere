"""The processing pipeline: which job kinds exist and which handler runs each one.

A stage gets a handler here only once it is implemented and tested.
"""

from __future__ import annotations

from seehere.jobs.worker import Handler

HANDLERS: dict[str, Handler] = {}
