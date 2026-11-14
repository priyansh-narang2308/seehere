"""`uv run python -m seehere.bench --annotation FILE --project UUID [--microsoft-vtt FILE]`."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from seehere.bench.annotation import AnnotationError, load
from seehere.bench.runner import markdown, run_item, write
from seehere.bench.systems import BenchError
from seehere.core.config import get_settings
from seehere.db.session import get_sessionmaker


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="seehere.bench", description=__doc__)
    p.add_argument("--annotation", type=Path, required=True)
    p.add_argument("--project", type=uuid.UUID, required=True, help="processed SeeHere project")
    p.add_argument("--microsoft-vtt", type=Path, help="GenerateAD output for the same video")
    p.add_argument("--out", type=Path, help="write <item>.json and <item>.md here")
    args = p.parse_args(argv)
    try:
        ann = load(args.annotation)
        cfg = get_settings()
        with get_sessionmaker()() as s:
            res = run_item(s, cfg, ann, args.project, args.microsoft_vtt)
    except (AnnotationError, BenchError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        for path in write(res, args.out):
            print(path)
    else:
        print(markdown(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
