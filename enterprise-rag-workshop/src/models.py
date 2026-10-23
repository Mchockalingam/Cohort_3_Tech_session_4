from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceDocument:
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TextChunk:
    id: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchHit:
    id: str
    text: str
    metadata: dict[str, Any]
    score: float
    method: str = "dense"


@dataclass
class EvidencePacket:
    text: str
    sources: dict[str, SearchHit] = field(default_factory=dict)
    token_count: int = 0
