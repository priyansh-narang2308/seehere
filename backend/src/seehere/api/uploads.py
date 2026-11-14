"""Receiving a raw upload body safely: size cap enforced from Content-Length and while bytes
arrive, streamed to a private temp file, hashed on the way."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import anyio
from fastapi import Request
from fastapi.concurrency import run_in_threadpool

from seehere.api.errors import APIError
from seehere.media.storage import MediaStore


@dataclass(frozen=True)
class Received:
    path: Path  # private temp file; the caller must delete or promote it
    size: int
    sha256: str


async def receive_upload(request: Request, store: MediaStore, cap: int, limit_mb: int) -> Received:
    limit_text = f"The limit is {limit_mb} MB."
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise APIError(400, "invalid_length", "Invalid Content-Length.")
        if int(declared) > cap:
            raise APIError(413, "too_large", f"The file is too large. {limit_text}")
    temp = await run_in_threadpool(store.new_temp_file)
    try:
        digest = hashlib.sha256()
        size = 0
        async with await anyio.open_file(temp, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > cap:
                    raise APIError(413, "too_large", f"The file is too large. {limit_text}")
                digest.update(chunk)
                await out.write(chunk)
        if size == 0:
            raise APIError(400, "empty_file", "The file is empty.")
    except BaseException:
        await run_in_threadpool(lambda: temp.unlink(missing_ok=True))
        raise
    return Received(temp, size, digest.hexdigest())
