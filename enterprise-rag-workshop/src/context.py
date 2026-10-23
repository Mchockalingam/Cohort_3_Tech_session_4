"""Build a bounded evidence packet with stable, auditable source identifiers."""

import tiktoken

from .models import EvidencePacket, SearchHit


_TOK = tiktoken.get_encoding("o200k_base")


def token_count(text: str) -> int:
    return len(_TOK.encode(text))


def build_packet(hits: list[SearchHit], max_tokens: int = 1200) -> EvidencePacket:
    if max_tokens < 64:
        raise ValueError("Use at least 64 tokens for source metadata and text")
    sources: dict[str, SearchHit] = {}
    blocks: list[str] = []
    seen: set[str] = set()
    separator = "\n--- EVIDENCE BOUNDARY ---\n"
    for hit in hits:
        if hit.id in seen:
            continue
        seen.add(hit.id)
        source_id = f"S{len(sources) + 1}"
        header = (
            f"[{source_id}] doc_id={hit.metadata['doc_id']} | "
            f"title={hit.metadata['title']} | version={hit.metadata['version']} | "
            f"page={hit.metadata.get('page', 1)} | path={hit.metadata['source_path']}\n"
        )
        # Re-measure the entire candidate because token counts do not always add
        # across concatenation boundaries.
        prefix = separator.join(blocks) + (separator if blocks else "")
        available = max_tokens - token_count(prefix + header) - 6
        if available < 15:
            break
        tokens = _TOK.encode(hit.text)
        allowed = min(len(tokens), available)
        excerpt = _TOK.decode(tokens[:allowed])
        if not excerpt.strip():
            continue
        block = f"{header}{excerpt}\n"
        while allowed > 0 and token_count(prefix + block) > max_tokens:
            allowed -= 1
            excerpt = _TOK.decode(tokens[:allowed])
            block = f"{header}{excerpt}\n"
        if allowed == 0 or not excerpt.strip():
            break
        blocks.append(block)
        sources[source_id] = hit
    packet_text = separator.join(blocks)
    return EvidencePacket(packet_text, sources, token_count(packet_text))
