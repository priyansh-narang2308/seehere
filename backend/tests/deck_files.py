"""Small real PDF and PPTX files for deck tests, built from scratch (no fixtures to trust)."""

from __future__ import annotations

import zipfile
from pathlib import Path


def make_pdf(pages: list[list[str]], out: Path) -> Path:
    """A valid PDF with a real text layer: one page per list, one text line per string."""
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_ref = 3 + 2 * n
    for i, lines in enumerate(pages):
        ops = ["BT", "/F1 24 Tf", "72 720 Td", "28 TL"]
        for line in lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({safe}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode()
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font_ref} 0 R >> >> >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    body = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(body)
    body += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    body += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    out.write_bytes(bytes(body))
    return out


_NS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)


def slide_xml(lines: list[str]) -> str:
    paras = "".join(f"<a:p><a:r><a:t>{line}</a:t></a:r></a:p>" for line in lines)
    body = f"<p:cSld><p:spTree><p:sp><p:txBody>{paras}</p:txBody></p:sp></p:spTree></p:cSld>"
    return f'<?xml version="1.0"?><p:sld {_NS}>{body}</p:sld>'


def make_pptx(slides: list[list[str]], out: Path, extra: dict[str, bytes] | None = None) -> Path:
    """The parts SeeHere reads from a PPTX: content types, presentation, and slides. Slide 10
    is written before slide 2 to prove ordering is numeric, not by zip order or name."""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("ppt/presentation.xml", f'<?xml version="1.0"?><p:presentation {_NS}/>')
        for i in sorted(range(len(slides)), key=lambda i: str(i + 1), reverse=True):
            z.writestr(f"ppt/slides/slide{i + 1}.xml", slide_xml(slides[i]))
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return out
