# 02 — Document loading, parsing and provenance

**Time: 15 minutes** · **Objective:** Parse enterprise source formats without discarding identity, security labels, document version or page references.

## What “loading” really means

Document loading is more than extracting text. A useful loader emits records containing text **plus** `doc_id`, title, source location, page, document type, service, version, effective date, status, tenant and allowed roles. Without these fields you cannot reliably cite, filter, suppress retired versions, or perform forensic review.

Enterprise inputs include PDF, DOCX, Markdown, TXT, HTML, tickets, wiki pages, tables, scanned forms and diagrams. This workshop implements the first four, then explains the additional production parsers required for rich layouts.

| Format | Demonstration parser | Correctness caveat |
|---|---|---|
| `.md`, `.txt` | UTF-8 file read | Code fences and headings should remain intact |
| Searchable `.pdf` | `pypdf.PdfReader(...).pages[i].extract_text()` | Scanned PDFs need OCR; tables, reading order and columns may be lost |
| `.docx` | `python-docx`, paragraphs and table rows in document order | Figures, tracked changes and merged cells require special handling |
| HTML, wiki, email, tickets | Not implemented | Add a trusted connector, schema mapping and HTML sanitizer |

## Code: inspect all catalogued source records

The full, reusable loader is in [`../src/loading.py`](../src/loading.py).

```python
from src.loading import load_catalog

records = load_catalog()
active = [record for record in records if record.metadata["status"] == "active"]

for record in active:
    m = record.metadata
    print({"id": m["doc_id"], "page": m["page"],
           "version": m["version"], "roles": m["allowed_roles"],
           "excerpt": record.text[:70]})
```

## Code: handle PDF and Word locally

The following illustrates the essential parsing operations (see the project loader for document order and metadata checks):

```python
from pathlib import Path
from pypdf import PdfReader
from docx import Document

def load_pdf(path: str):
    reader = PdfReader(path)
    for page_num, page in enumerate(reader.pages, start=1):
        yield {"page": page_num, "text": page.extract_text() or "",
               "source": Path(path).name}

def load_docx(path: str):
    file = Document(path)
    text_parts = []
    for block in file.iter_inner_content():
        if hasattr(block, "rows"):
            for row in block.rows:
                text_parts.append(" | ".join(cell.text for cell in row.cells))
        elif block.text.strip():
            text_parts.append(block.text.strip())
    return "\n".join(text_parts)
```

## Lab: identify what should *not* be indexed

```bash
python -m src.cli load
```

1. Locate `RUN-PAY-OLD` and the reason it should not appear in retrieval.
2. Locate `SEC-FRAUD-009` and identify its permitted role.
3. Explain how a PDF page reference could appear in a generated citation.

## Enterprise decisions before a loader goes live

- **Source connectors:** authenticate to SharePoint, Confluence, object storage or document management systems with restricted, auditable service identities.
- **ACL propagation:** track entitlement changes and revoke indexed access quickly; multi-tenant isolation is mandatory.
- **Updates/deletions:** define versioned source IDs, content hashes, tombstones and complete reindex/reconciliation workflows. `upsert` alone does **not** remove obsolete chunks.
- **Text integrity:** preserve tables, section headings, code and units; detect OCR errors, duplicated headers/footers and hidden content.
- **Privacy:** redact or exclude secrets and regulated identifiers before embeddings or external model calls; require retention/data-residency review.
- **Content trust:** malware scan and vet origin; a retrieved document can carry prompt injection.

**Failure demonstration:** A search result sourced from the obsolete rollback procedure could tell engineers to restart a production database without approval. Active/retired status is a safety requirement, not cosmetic metadata.

**Next:** [03 — Chunking strategies](03-text-chunking.md). [Parsing references](../references.md).
