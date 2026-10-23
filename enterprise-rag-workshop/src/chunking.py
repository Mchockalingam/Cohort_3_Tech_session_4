"""Transparent teaching implementations of major chunking families."""

import hashlib
import re
from collections.abc import Callable

from .models import SourceDocument, TextChunk


def _check(size: int, overlap: int = 0) -> None:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")


def fixed_char(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    _check(size, overlap)
    step = size - overlap
    return [text[i : i + size] for i in range(0, len(text), step) if text[i : i + size]]


def fixed_token(text: str, size: int = 160, overlap: int = 30) -> list[str]:
    """Exact token windows under a chosen tokenizer, not a character heuristic."""
    _check(size, overlap)
    import tiktoken

    encoder = tiktoken.get_encoding("o200k_base")
    tokens = encoder.encode(text)
    return [encoder.decode(tokens[i : i + size]) for i in range(0, len(tokens), size - overlap)]


def _sentence_units(text: str) -> list[str]:
    # An instructional heuristic; use locale-specific sentence segmentation in production.
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9#`])", text) if s.strip()]


def sentence_window(text: str, window: int = 3, step: int = 2) -> list[str]:
    if window <= 0 or step <= 0:
        raise ValueError("window and step must be positive")
    sentences = _sentence_units(text)
    return [" ".join(sentences[i : i + window]) for i in range(0, len(sentences), step)]


def paragraphs(text: str, size: int = 700) -> list[str]:
    _check(size)
    blocks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    result = []
    for p in blocks:
        result.extend([p] if len(p) <= size else fixed_char(p, size, 0))
    return result


def _pack(units: list[str], size: int, overlap: int = 0) -> list[str]:
    _check(size, overlap)
    result, current = [], ""
    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        if len(unit) > size:
            if current:
                result.append(current)
                current = ""
            result.extend(fixed_char(unit, size, overlap))
            continue
        joined = (current + "\n" + unit).strip() if current else unit
        if len(joined) <= size:
            current = joined
        else:
            if current:
                result.append(current)
            tail = current[-overlap:] if overlap else ""
            # Start the repeated tail at a word boundary where practical.
            if tail and len(current) > overlap and " " in tail:
                tail = tail.split(" ", 1)[1]
            current = (tail + "\n" + unit).strip() if len(tail) + len(unit) + 1 <= size else unit
    if current:
        result.append(current)
    return result


def recursive(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    """Prefer paragraphs, then lines, then sentences, then words, then characters."""
    _check(size, overlap)
    if len(text) <= size:
        return [text.strip()] if text.strip() else []

    def split_large(block: str, separators: list[str]) -> list[str]:
        if len(block) <= size:
            return [block]
        if not separators:
            return fixed_char(block, size, 0)
        sep = separators[0]
        pieces = block.split(sep)
        if len(pieces) == 1:
            return split_large(block, separators[1:])
        out = []
        for index, part in enumerate(pieces):
            # Keep sentence punctuation; a naive `.split(". ")` drops it.
            if sep == ". " and index < len(pieces) - 1:
                part += "."
            if part.strip():
                out.extend(split_large(part.strip(), separators[1:]))
        return out

    return _pack(split_large(text, ["\n\n", "\n", ". ", " "]), size, overlap)


def markdown_headings(text: str, size: int = 700, overlap: int = 80) -> list[str]:
    """Preserve heading lineage as context; then chunk within each section."""
    headings: dict[int, str] = {}
    sections: list[tuple[str, str]] = []
    body: list[str] = []

    def flush() -> None:
        if body:
            path = " > ".join(headings[level] for level in sorted(headings))
            sections.append((path, "\n".join(body)))
            body.clear()

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            flush()
            depth = len(match.group(1))
            headings = {k: v for k, v in headings.items() if k < depth}
            headings[depth] = match.group(2).strip()
            body.append(line)
        else:
            body.append(line)
    flush()
    result = []
    for path, section in sections:
        prefix = (f"Section: {path}\n" if path else "")
        if len(prefix) >= size:
            prefix = prefix[: max(0, size // 3)] + "\n"
        # Repeat section lineage on *every* continuation chunk, not only chunk 1.
        for part in recursive(section, size - len(prefix), min(overlap, max(0, size - len(prefix) - 1))):
            result.append(prefix + part)
    return result


def semantic(text: str, embed_sentences: Callable[[list[str]], list[list[float]]],
             threshold: float = 0.72, max_chars: int = 700) -> list[str]:
    """Break on semantic discontinuity, capped by maximum size; embeddings are normalized."""
    import numpy as np

    sentences = _sentence_units(text)
    if not sentences:
        return []
    vectors = np.asarray(embed_sentences(sentences), dtype=float)
    if vectors.shape[0] != len(sentences):
        raise ValueError("Embedding count must equal sentence count")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)
    groups, current = [], [sentences[0]]
    for i in range(1, len(sentences)):
        similar = float(np.dot(vectors[i - 1], vectors[i]))
        candidate = " ".join(current + [sentences[i]])
        if similar < threshold or len(candidate) > max_chars:
            groups.extend(recursive(" ".join(current), max_chars, 0))
            current = [sentences[i]]
        else:
            current.append(sentences[i])
    groups.extend(recursive(" ".join(current), max_chars, 0))
    return groups


def table_aware(text: str, size: int = 700) -> list[str]:
    """Keep small Markdown tables atomic; repeat header on row-wise oversized splits."""
    blocks = [block for block in re.split(r"\n\s*\n", text) if block.strip()]
    output = []
    for block in blocks:
        lines = block.splitlines()
        is_table = len(lines) >= 2 and all(line.lstrip().startswith("|") for line in lines)
        if not is_table:
            output.extend(recursive(block, size, 0))
        elif len(block) <= size:
            output.append(block)
        else:
            header = "\n".join(lines[:2])
            rows = _pack(lines[2:], max(1, size - len(header) - 1), 0)
            output.extend(header + "\n" + rows_part for rows_part in rows)
    return output


def code_fence_aware(text: str, size: int = 700) -> list[str]:
    """Preserve short fenced code blocks; large blocks need AST/symbol-aware parsing."""
    pattern = re.compile(r"(?ms)^```[^\n]*\n.*?^```\s*$")
    result, cursor = [], 0
    for match in pattern.finditer(text):
        result.extend(recursive(text[cursor:match.start()], size, 0))
        snippet = match.group()
        result.extend([snippet] if len(snippet) <= size else fixed_char(snippet, size, 0))
        cursor = match.end()
    result.extend(recursive(text[cursor:], size, 0))
    return result


def create_chunks(doc: SourceDocument, strategy: str = "headings", size: int = 700,
                  overlap: int = 100, embed_sentences=None) -> list[TextChunk]:
    strategies = {
        "characters": lambda: fixed_char(doc.text, size, overlap),
        "tokens": lambda: fixed_token(doc.text, max(1, size // 4), max(0, overlap // 4)),
        "sliding": lambda: fixed_char(doc.text, size, overlap),
        "sentences": lambda: sentence_window(doc.text),
        "paragraphs": lambda: paragraphs(doc.text, size),
        "recursive": lambda: recursive(doc.text, size, overlap),
        "headings": lambda: markdown_headings(doc.text, size, overlap),
        "semantic": lambda: semantic(doc.text, embed_sentences, max_chars=size),
        "tables": lambda: table_aware(doc.text, size),
        "code": lambda: code_fence_aware(doc.text, size),
    }
    if strategy not in strategies:
        raise ValueError(f"Unknown strategy {strategy}; choose from {list(strategies)}")
    if strategy == "semantic" and embed_sentences is None:
        raise ValueError("Semantic chunking requires an embedding callback")
    pieces = strategies[strategy]()
    chunks = []
    for index, part in enumerate(pieces):
        if not part.strip():
            continue
        basis = f"{doc.metadata['doc_id']}:{doc.metadata['version']}:{doc.metadata['page']}:{strategy}:{index}:{part}"
        chunk_id = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
        meta = dict(doc.metadata)
        meta.update({"chunk_index": index, "strategy": strategy})
        chunks.append(TextChunk(chunk_id, part.strip(), meta))
    return chunks


def parent_child(doc: SourceDocument, parent_size: int = 1400, child_size: int = 350):
    """Return child chunks and explicit parent lookup for small-to-big retrieval."""
    parent_pieces = recursive(doc.text, parent_size, 0)
    parent_lookup: dict[str, str] = {}
    children: list[TextChunk] = []
    for i, parent_text in enumerate(parent_pieces):
        parent_id = f"{doc.metadata['doc_id']}:{doc.metadata['version']}:parent:{i}"
        parent_lookup[parent_id] = parent_text
        temp = SourceDocument(parent_text, dict(doc.metadata))
        for child in create_chunks(temp, "recursive", child_size, 0):
            enriched = {**child.metadata, "parent_id": parent_id}
            children.append(TextChunk(f"{child.id}-{i}", child.text, enriched))
    return children, parent_lookup
