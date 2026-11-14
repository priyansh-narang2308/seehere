"""Optional slide deck (PDF or PPTX): per-page text, aligned to the keyframe where it appears.

The deck is the cleanest source of on-screen text (no OCR errors), so later stages can prefer
it. Pages are aligned to keyframes by comparing the page text with the keyframe's OCR text.

Security: decks are untrusted files.
- Identified by content (magic bytes and structure), never by extension.
- PDF via pypdf (BSD). Encrypted PDFs are refused; the page count is capped.
- PPTX is read in memory with zipfile; nothing is extracted to disk. Entry count, per-entry and
  total uncompressed size and compression ratio are capped before any entry is read (zip-bomb
  guard), entry names with `..` or absolute paths are refused (path guard), and XML is parsed
  with defusedxml (no entity expansion or external entities).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from defusedxml import DefusedXmlException, ElementTree
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PAGES = 300
MAX_ZIP_ENTRIES = 3000
MAX_ENTRY_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 300 * 1024 * 1024
MAX_RATIO = 100  # uncompressed / compressed, per entry

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_SLIDE_NAME = re.compile(r"^ppt/slides/slide(\d+)\.xml$")


class DeckRejected(Exception):
    """The file is not a usable deck. `message` is safe to show to users."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class DeckType:
    kind: str  # "pdf" or "pptx"
    extension: str
    mime_type: str


PDF = DeckType("pdf", ".pdf", "application/pdf")
PPTX = DeckType(
    "pptx", ".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
UNSUPPORTED = "This file is not a supported slide deck. Upload a PDF or PPTX file."


def identify_deck(path: Path) -> DeckType:
    with path.open("rb") as f:
        head = f.read(8)
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as z:
                names = set(z.namelist())
        except zipfile.BadZipFile as exc:
            raise DeckRejected(UNSUPPORTED) from exc
        if "[Content_Types].xml" in names and "ppt/presentation.xml" in names:
            return PPTX
    raise DeckRejected(UNSUPPORTED)


def _clean(text: str) -> str:
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def extract_pdf(path: Path) -> list[str]:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise DeckRejected("This PDF is password-protected. Upload an unprotected copy.")
        if len(reader.pages) > MAX_PAGES:
            raise DeckRejected(f"This deck has more than {MAX_PAGES} pages.")
        return [_clean(page.extract_text() or "") for page in reader.pages]
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise DeckRejected("This PDF could not be read.") from exc


def _check_zip(z: zipfile.ZipFile) -> None:
    infos = z.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise DeckRejected("This PPTX file has too many parts.")
    total = 0
    for info in infos:
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in Path(name).parts or ":" in name:
            raise DeckRejected(UNSUPPORTED)
        if info.file_size > MAX_ENTRY_BYTES:
            raise DeckRejected("This PPTX file contains a part that is too large.")
        if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
            raise DeckRejected("This PPTX file is compressed suspiciously and was refused.")
        total += info.file_size
    if total > MAX_TOTAL_BYTES:
        raise DeckRejected("This PPTX file is too large when unpacked.")


def extract_pptx(path: Path) -> list[str]:
    """Slide text in slide-number order, one string per slide, one line per paragraph."""
    try:
        with zipfile.ZipFile(path) as z:
            _check_zip(z)
            slides = sorted(
                (int(m.group(1)), name) for name in z.namelist() if (m := _SLIDE_NAME.match(name))
            )
            if len(slides) > MAX_PAGES:
                raise DeckRejected(f"This deck has more than {MAX_PAGES} slides.")
            out = []
            for _, name in slides:
                root = ElementTree.fromstring(z.read(name))
                paragraphs = [
                    "".join(t.text or "" for t in p.iter(f"{_A}t")) for p in root.iter(f"{_A}p")
                ]
                out.append(_clean("\n".join(paragraphs)))
            return out
    except DeckRejected:
        raise
    except DefusedXmlException as exc:  # entity expansion, external entities, DTDs
        raise DeckRejected("This PPTX file contains forbidden XML and was refused.") from exc
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, ValueError) as exc:
        raise DeckRejected("This PPTX file could not be read.") from exc


def extract_pages(path: Path, deck: DeckType) -> list[str]:
    return extract_pdf(path) if deck is PDF else extract_pptx(path)


# --- alignment ---

_TOKEN = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")


def tokens(text: str) -> set[str]:
    """Words of 3+ letters and all numbers, lower-cased: enough to tell slides apart."""
    return {t for t in _TOKEN.findall(text.lower()) if len(t) >= 3 or t[0].isdigit()}


def similarity(page: str, screen: str) -> float:
    """Share of the page's distinctive tokens that OCR found on screen, weighted toward
    pages and screens that agree in both directions (Dice coefficient)."""
    a, b = tokens(page), tokens(screen)
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


@dataclass(frozen=True)
class Alignment:
    frame_index: int | None  # index into the keyframes given, or None
    score: float


def align(pages: list[str], screens: list[str], threshold: float) -> list[Alignment]:
    """Best-matching keyframe for each page; below `threshold` the page stays unaligned (it
    may not have been shown, or its screen text was unreadable)."""
    out = []
    for page in pages:
        scores = [similarity(page, s) for s in screens]
        best = max(range(len(scores)), key=scores.__getitem__, default=None)
        if best is None or scores[best] < threshold:
            out.append(Alignment(None, round(max(scores, default=0.0), 4)))
        else:
            out.append(Alignment(best, round(scores[best], 4)))
    return out
