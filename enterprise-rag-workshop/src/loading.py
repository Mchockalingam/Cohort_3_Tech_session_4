"""Trusted-catalog document loading; OCR and complex layouts need production parsers."""

import json
from pathlib import Path

from .models import SourceDocument


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog.json"


def _read_pages(path: Path) -> list[tuple[int, str]]:
    ext = path.suffix.lower()
    if ext in {".txt", ".md"}:
        return [(1, path.read_text(encoding="utf-8"))]
    if ext == ".pdf":
        from pypdf import PdfReader  # optional until a PDF is actually loaded

        reader = PdfReader(str(path))
        return [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, 1)]
    if ext == ".docx":
        from docx import Document
        from docx.table import Table

        document = Document(str(path))
        parts = []
        for block in document.iter_inner_content():
            if isinstance(block, Table):
                for row in block.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            elif block.text.strip():
                level = block.style.name if block.style else ""
                prefix = "# " if level == "Heading 1" else "## " if level == "Heading 2" else ""
                parts.append(prefix + block.text.strip())
        return [(1, "\n\n".join(parts))]
    raise ValueError(f"Unsupported file type: {ext}")


def load_catalog(catalog_path: Path = DEFAULT_CATALOG) -> list[SourceDocument]:
    """Load and validate metadata before indexing. In production, use a signed/approved catalog."""
    catalog_path = Path(catalog_path).resolve()
    base = catalog_path.parent
    entries = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("Catalog must contain a list")
    documents: list[SourceDocument] = []
    seen = set()
    for entry in entries:
        doc_id = entry["doc_id"]
        if doc_id in seen:
            raise ValueError(f"Duplicate doc_id: {doc_id}")
        seen.add(doc_id)
        if entry["status"] not in {"active", "retired"}:
            raise ValueError(f"Invalid document status: {doc_id}")
        if not entry["allowed_roles"] or not all(isinstance(r, str) for r in entry["allowed_roles"]):
            raise ValueError(f"Missing allowed_roles: {doc_id}")
        path = (base / entry["file"]).resolve()
        if not path.is_relative_to(base):
            raise ValueError(f"Catalog path escapes its root: {doc_id}")
        if not path.is_file():
            raise FileNotFoundError(path)
        for page, raw in _read_pages(path):
            content = raw.replace("\u00a0", " ").strip()
            if not content:
                continue
            metadata = {k: v for k, v in entry.items() if k != "file"}
            metadata.update({"source_path": str(path.relative_to(PROJECT_ROOT)), "page": page})
            documents.append(SourceDocument(content, metadata))
    return documents
