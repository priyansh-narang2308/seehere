"""Path safety and filename sanitizing (no network, no database)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from seehere.media.storage import MediaStore, UnsafePathError, sanitize_filename, source_video_path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("lecture.mp4", "lecture.mp4"),
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32\\evil.mp4", "evil.mp4"),
        ("/absolute/path/talk.mov", "talk.mov"),
        (".hidden.mp4", "hidden.mp4"),
        ("bad\x00name\x1f.mp4", "badname.mp4"),
        ('what?<>:"|*.mp4', "what.mp4"),
        ("", "upload"),
        ("..", "upload"),
        ("Vorlesung über Daten — Teil 1.mp4", "Vorlesung über Daten — Teil 1.mp4"),
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_caps_utf8_bytes() -> None:
    name = sanitize_filename("é" * 300 + ".mp4")
    assert len(name.encode("utf-8")) <= 255


@pytest.mark.parametrize(
    "relative", ["../outside", "a/../../outside", "/etc/passwd", "", ".", "x\x00y"]
)
def test_resolve_refuses_escapes(tmp_path: Path, relative: str) -> None:
    with pytest.raises(UnsafePathError):
        MediaStore(tmp_path / "media").resolve(relative)


def test_resolve_refuses_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("no")
    (root / "link").symlink_to(tmp_path)
    store = MediaStore(root)
    with pytest.raises(UnsafePathError):
        store.resolve("link/secret.txt")
    assert store.resolve("projects/a/source.mp4") == (root / "projects/a/source.mp4").resolve()


def test_temp_files_are_private_and_unique(tmp_path: Path) -> None:
    store = MediaStore(tmp_path)
    a, b = store.new_temp_file(), store.new_temp_file()
    assert a != b
    assert a.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "tmp").stat().st_mode & 0o777 == 0o700


def test_source_video_path_only_accepts_simple_extensions() -> None:
    pid = uuid.uuid4()
    assert source_video_path(pid, ".mp4") == f"projects/{pid}/source.mp4"
    for bad in ("mp4", ".mp4/../../x", ".MP4", "./"):
        with pytest.raises(UnsafePathError):
            source_video_path(pid, bad)
