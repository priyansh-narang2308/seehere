"""Slide decks: real PDF/PPTX parsing, hostile files, alignment, and the upload-to-aligned flow."""

from __future__ import annotations

import io
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest
from deck_files import make_pdf, make_pptx
from fastapi.testclient import TestClient
from pipeline_project import add_project, run_jobs
from pypdf import PdfReader, PdfWriter
from slide_images import SLIDE_1, SLIDE_2, make_deck_video
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.session import get_db
from seehere.slides.deck import (
    PDF,
    PPTX,
    DeckRejected,
    align,
    extract_pdf,
    extract_pptx,
    identify_deck,
    similarity,
)

Sessions = sessionmaker[Session]
ACTION = {"X-SeeHere-Request": "1"}
DECK_CHAIN = ("media.prepare", "scenes.detect", "ocr.extract", "deck.ingest")
TEXT_1 = [t for t, *_ in SLIDE_1]
TEXT_2 = [t for t, *_ in SLIDE_2]
APPENDIX = ["Appendix", "Further reading and references"]


# --- parsing ---


def test_pdf_pages_are_read(tmp_path: Path) -> None:
    pdf = make_pdf([TEXT_1, TEXT_2], tmp_path / "d.pdf")
    assert identify_deck(pdf) is PDF
    assert extract_pdf(pdf) == ["\n".join(TEXT_1), "\n".join(TEXT_2)]


def test_pptx_slides_are_read_in_numeric_order(tmp_path: Path) -> None:
    slides = [[f"Slide {n}"] for n in range(1, 12)]
    pptx = make_pptx(slides, tmp_path / "d.pptx")
    assert identify_deck(pptx) is PPTX
    assert extract_pptx(pptx) == [f"Slide {n}" for n in range(1, 12)]


def test_unsupported_files_are_refused(tmp_path: Path) -> None:
    for name, data in [
        ("x.pdf", b"not a pdf"),
        ("x.zip", _zip({"hello.txt": b"hi"})),  # a zip, but not a presentation
        ("x.docx", _zip({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w/>"})),
        ("x.pptx", b"PK\x03\x04 truncated"),
    ]:
        path = tmp_path / name
        path.write_bytes(data)
        with pytest.raises(DeckRejected, match="not a supported slide deck"):
            identify_deck(path)


def test_encrypted_and_corrupt_pdfs_are_refused(tmp_path: Path) -> None:
    writer = PdfWriter(clone_from=PdfReader(make_pdf([TEXT_1], tmp_path / "plain.pdf")))
    writer.encrypt("secret")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as f:
        writer.write(f)
    with pytest.raises(DeckRejected, match="password-protected"):
        extract_pdf(locked)
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4\n" + b"\x00garbage" * 50)
    with pytest.raises(DeckRejected, match="could not be read"):
        extract_pdf(broken)


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_zip_bomb_is_refused_before_reading(tmp_path: Path) -> None:
    bomb = make_pptx([["Hi"]], tmp_path / "bomb.pptx", {"ppt/media/zeros.bin": b"\0" * 5_000_000})
    with pytest.raises(DeckRejected, match="compressed suspiciously"):
        extract_pptx(bomb)


def test_path_traversal_names_are_refused(tmp_path: Path) -> None:
    evil = make_pptx([["Hi"]], tmp_path / "evil.pptx", {"../../etc/evil.xml": b"<x/>"})
    with pytest.raises(DeckRejected, match="not a supported slide deck"):
        extract_pptx(evil)


def test_too_many_parts_are_refused(tmp_path: Path) -> None:
    many = {f"ppt/junk/{i}.xml": b"<x/>" for i in range(3001)}
    with pytest.raises(DeckRejected, match="too many parts"):
        extract_pptx(make_pptx([["Hi"]], tmp_path / "many.pptx", many))


def test_xml_entity_expansion_is_refused(tmp_path: Path) -> None:
    laughs = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE sld [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        '<sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<a:p><a:r><a:t>&b;</a:t></a:r></a:p></sld>"
    )
    path = tmp_path / "laughs.pptx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/presentation.xml", "<p/>")
        z.writestr("ppt/slides/slide1.xml", laughs)
    with pytest.raises(DeckRejected, match="forbidden XML"):
        extract_pptx(path)


# --- alignment ---


def test_alignment_picks_the_matching_screen_and_leaves_unshown_pages() -> None:
    screens = ["\n".join(TEXT_1), "next steps\nhire 3 engineers by march", ""]
    pages = ["\n".join(TEXT_2), "\n".join(TEXT_1), "\n".join(APPENDIX)]
    result = align(pages, screens, threshold=0.4)
    assert [a.frame_index for a in result] == [1, 0, None]
    assert result[1].score == 1.0
    assert similarity("", "anything") == 0.0
    assert align(pages, [], threshold=0.4)[0].frame_index is None


def test_ocr_mistakes_still_align() -> None:
    page = "\n".join(TEXT_1)
    misread = "Quarterlv Revenue\nRevenue rose 12.5% to $3.2M\nOperating rnargin 41.7% in 2022"
    assert similarity(page, misread) > 0.6


# --- API and pipeline ---


@pytest.fixture(scope="module")
def deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_deck_video(tmp_path_factory.mktemp("deck"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)


@pytest.fixture
def client(sessions: Sessions, settings: Settings) -> Iterator[TestClient]:
    def db() -> Iterator[Session]:
        with sessions() as s:
            yield s

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _post_deck(client: TestClient, pid: uuid.UUID, path: Path, **headers: str):  # type: ignore[no-untyped-def]
    return client.post(
        f"/api/projects/{pid}/deck",
        content=path.read_bytes(),
        headers={"X-SeeHere-Filename": quote(path.name), **ACTION, **headers},
    )


def test_upload_then_pages_align_to_keyframes(
    client: TestClient,
    sessions: Sessions,
    settings: Settings,
    deck: Path,
    tmp_path: Path,
) -> None:
    pid = add_project(sessions, settings, deck)
    assert client.get(f"/api/projects/{pid}/deck").json()["available"] is False
    pptx = make_pptx([TEXT_1, TEXT_2, APPENDIX], tmp_path / "lecture.pptx")

    r = _post_deck(client, pid, pptx)
    assert r.status_code == 201, r.text
    assert (r.json()["filename"], r.json()["kind"], r.json()["ingested"]) == (
        "lecture.pptx",
        "pptx",
        False,
    )
    run_jobs(sessions, settings, DECK_CHAIN)  # the deck is read, then realigned once OCR finishes

    body = client.get(f"/api/projects/{pid}/deck").json()
    assert body["ingested"] is True
    pages = body["pages"]
    assert [p["page"] for p in pages] == [1, 2, 3]
    assert [p["t_s"] for p in pages] == [0.0, 5.0, None]  # the appendix was never shown
    assert pages[0]["score"] > 0.8 and pages[1]["score"] > 0.8 and pages[2]["score"] < 0.4
    assert pages[0]["text"] == "\n".join(TEXT_1)
    labels = [j["label"] for j in client.get(f"/api/projects/{pid}/jobs").json()["jobs"]]
    assert "Slide deck" in labels


def test_replacing_a_deck_removes_the_old_one(
    client: TestClient,
    sessions: Sessions,
    settings: Settings,
    deck: Path,
    tmp_path: Path,
) -> None:
    pid = add_project(sessions, settings, deck)
    assert _post_deck(client, pid, make_pptx([TEXT_1], tmp_path / "a.pptx")).status_code == 201
    assert _post_deck(client, pid, make_pdf([TEXT_2], tmp_path / "b.pdf")).status_code == 201
    files = sorted(p.name for p in (settings.media_dir / "projects" / str(pid)).glob("deck-*"))
    assert len(files) == 1 and files[0].endswith(".pdf")
    run_jobs(sessions, settings, DECK_CHAIN)
    body = client.get(f"/api/projects/{pid}/deck").json()
    assert (body["filename"], body["kind"], [p["page"] for p in body["pages"]]) == (
        "b.pdf",
        "pdf",
        [1],
    )


def test_deck_upload_rules(
    client: TestClient,
    sessions: Sessions,
    settings: Settings,
    deck: Path,
    tmp_path: Path,
) -> None:
    pid = add_project(sessions, settings, deck)
    pdf = make_pdf([TEXT_1], tmp_path / "d.pdf")
    r = client.post(f"/api/projects/{pid}/deck", content=pdf.read_bytes())
    assert (r.status_code, r.json()["error"]["code"]) == (403, "missing_request_header")
    junk = tmp_path / "notes.txt"
    junk.write_text("just notes")
    r = _post_deck(client, pid, junk)
    assert (r.status_code, r.json()["error"]["code"]) == (415, "unsupported_deck")
    assert r.json()["error"]["message"].startswith("This file is not a supported slide deck")
    assert _post_deck(client, uuid.uuid4(), pdf).status_code == 404
    settings.max_deck_mb = 1
    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024))
    r = _post_deck(client, pid, big)
    assert (r.status_code, r.json()["error"]["code"]) == (413, "too_large")
    assert not list((settings.media_dir / "projects" / str(pid)).glob("deck-*"))
    assert not list((settings.media_dir / "tmp").glob("*"))
