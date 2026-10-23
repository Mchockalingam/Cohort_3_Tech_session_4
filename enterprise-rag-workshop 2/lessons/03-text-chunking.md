# 03 — Text chunking: strategy guide and runnable comparisons

**Time: 25 minutes** · **Objective:** Select, implement and evaluate a chunking strategy based on source structure, task, recall and evidence completeness.

## Why chunking matters

An entire 100-page policy is too diffuse to retrieve as one embedding. A 20-word chunk can lose the approval condition attached to the next sentence. Chunking decides what *unit of meaning* is indexed, how much overlap is repeated and which source/section metadata survives.

**There is no universally optimal chunk size or literally exhaustive list of methods.** Below are the major practical families; **11 patterns are exercised in the project** (10 named CLI strategies plus parent–child), and advanced alternatives are discussed afterwards.

| Strategy | Mechanism | Advantage | Typical failure |
|---|---|---|---|
| 1. Fixed character | Cut every N characters | Fast, deterministic | Splits words, units and tables |
| 2. Fixed token | Cut exact tokenizer windows | Predictable embedding budget | Splits a sentence or clause |
| 3. Overlapping/sliding | Window + repeated tail | Recovers boundary context | Duplicate evidence, storage growth |
| 4. Sentence window | Group N sentences; stride M | Good atomic assertions | Long sentences, abbreviation splits |
| 5. Paragraph | Blank-line boundaries | Natural prose sections | Inconsistent author formatting |
| 6. Recursive separators | Paragraph → line → sentence → word → character | Sensible general-purpose baseline | Imperfect hierarchy; code/table breakage |
| 7. Markdown heading | Keep section/heading lineage | Policy and runbook context | Very large sections still need splitting |
| 8. Semantic | Split at low adjacent sentence similarity | Topic cohesion | Embedding cost, missed transitions |
| 9. Table-aware | Preserve header and table rows | Units, pricing, SLO tables | Complex spans and huge tables |
| 10. Code-fence aware | Preserve fenced code blocks | Better than prose split for scripts | Large functions need AST parser |
| 11. Parent–child / small-to-big | Index small child; display authorised larger parent | Precision + explanation context | Re-expansion must preserve ACLs |

### More advanced families (not covered in this session)

- **Layout/page/element aware:** preserve PDF reading order, headings, captions and table geometry (often requires layout models/OCR).
- **AST/symbol aware:** chunk functions, classes and imports for repositories; preserve dependency paths.
- **Contextual enrichment:** prepend approved title/section/description to every chunk; measure whether it improves retrieval and avoid inventing context.
- **Late chunking:** create contextual token representations over a larger document and pool at chunk boundaries; requires a compatible long-context token embedding model.
- **LLM/agent-proposed boundaries:** ask a model to identify semantic units, but validate boundaries against original offsets and constrain cost/hallucination.
- **Proposition/atomic claim extraction:** useful for exact facts but risky when extraction drops negation or qualifications.
- **Multimodal chunking:** attach OCR text, image caption, layout coordinates and visual embeddings to page/figure anchors.

## Runnable implementations

All major implementations are in [`../src/chunking.py`](../src/chunking.py). This snippet compares outcomes on the same source:

```python
from src.loading import load_catalog
from src.chunking import create_chunks

doc = next(d for d in load_catalog() if d.metadata["doc_id"] == "RUN-DB-201")
for strategy in ("characters", "tokens", "sliding", "sentences",
                 "paragraphs", "recursive", "headings", "tables", "code"):
    pieces = create_chunks(doc, strategy=strategy, size=450, overlap=75)
    lengths = [len(p.text) for p in pieces]
    print(strategy, "count", len(pieces), "sizes", lengths)
```

Fixed character and token windows use different units. The core loop for character windows is:

```python
def char_windows(text: str, size: int, overlap: int):
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Invalid size or overlap")
    for start in range(0, len(text), size - overlap):
        yield text[start:start + size]
```

For a **true token** boundary, `tiktoken` is applied *before* slicing. Token counts depend on the selected tokenizer and are not identical to characters/4:

```python
import tiktoken

enc = tiktoken.get_encoding("o200k_base")
tokens = enc.encode(doc.text)
for start in range(0, len(tokens), 160 - 30):
    print(enc.decode(tokens[start:start + 160])[:80])
```

These windows may split multibyte text at a tokenizer boundary or a sentence in half; use structure-aware approaches for production evidence spans.

## Semantic chunking: inspect topic boundaries

Semantic chunking embeds **sentences**, compares adjacent vectors, and starts a new chunk when cosine similarity drops below a chosen threshold (here, an **illustrative** 0.72, not a benchmarked universal value). Always cap length as well.

```python
from src.chunking import semantic
from src.embeddings import LocalEncoder

model = LocalEncoder()
sections = semantic(doc.text, model.documents, threshold=0.72, max_chars=500)
for n, section in enumerate(sections, 1):
    print(n, len(section), section[:120])
```

## Parent–child / small-to-big example

Index the short *child* but expand to its parent only **after authorisation**. The parent store is also access-controlled in production.

```python
from src.chunking import parent_child

children, parent_lookup = parent_child(doc, parent_size=900, child_size=250)
match = children[0]                       # standing in for a retrieved child
parent_text = parent_lookup[match.metadata["parent_id"]]
print("Child indexed:\n", match.text[:140])
print("Parent evidence:\n", parent_text[:280])
```

## Structure-aware table and code demonstration

```python
from src.chunking import table_aware, code_fence_aware

table = "| Condition | Action |\n|---|---|\n| P1 | Alert commander |"
print(table_aware("Before\n\n" + table, size=180))

script = "# Deployment notes\n\n```bash\necho 'dry run only'\n```"
print(code_fence_aware(script, size=180))
```

The code-fence approach is intentionally introductory; a production code RAG system should prefer AST-aware chunking with module/symbol references.

## Four engineering choices to teach

1. **Boundary integrity:** an emergency-approval requirement must remain attached to the associated rollback condition.
2. **Metadata invariants:** every chunk keeps `doc_id`, version, status, access labels, page and path.
3. **Size/overlap experiment:** compare approximately 300/50, 550/80 and 900/120 characters *on the supplied dataset*. Avoid pretending character settings equal token settings.
4. **Test by retrieval**, not by how coherent the chunks appear. Judge recall@k, support completeness, citation quality, duplicates, latency and cost against labelled questions.

## Lab: split and explain

```bash
python -m src.cli chunk --strategy characters
python -m src.cli chunk --strategy recursive
python -m src.cli chunk --strategy headings
python -m src.cli chunk --strategy semantic
```

Discuss: Which chunk contains the database saturation threshold *and* relevant mitigation steps? Which strategy makes it easiest to cite a specific runbook section? For this structured Markdown catalog, **heading-aware recursive splitting** is our teachable default; it is not a blanket production recommendation.

**Reference** - https://www.nb-data.com/p/9-chunking-strategis-to-improve-rag

**Next:** [04 — Embeddings](04-embeddings.md). [Chunking documentation](../references.md).
