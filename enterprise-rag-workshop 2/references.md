# Official references and further reading

**Research checked: 23 October 2026.** These are primary vendor/maintainer or security-project sources used to validate APIs and the design rationale. APIs may change; pin and internally validate dependency versions before a class.

## Parsing, chunking and embeddings

1. [Sentence Transformers: semantic search](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html) — asymmetric retrieval; query/document encoding and nearest-neighbour methods.
2. [Sentence Transformers: model API](https://sbert.net/docs/package_reference/sentence_transformer/model.html) — `encode_document`, `encode_query`, `normalize_embeddings`.
3. [LlamaIndex: semantic splitter](https://docs.llamaindex.ai/en/stable/api_reference/node_parsers/semantic_splitter/) — semantically sensitive boundaries.
4. [Unstructured: chunking](https://docs.unstructured.io/api-reference/partition/chunking) — partitioning into semantic elements and table-preserving chunking.
5. [pypdf documentation](https://pypdf.readthedocs.io/en/stable/) — extraction of searchable PDF text (does not replace OCR).
6. [python-docx documentation](https://python-docx.readthedocs.io/en/latest/) — Word paragraphs and tables.

## Vector database and retrieval

7. [Chroma: collection configuration](https://docs.trychroma.com/docs/collections/configure) — HNSW distance spaces, including cosine.
8. [Chroma: query and get](https://docs.trychroma.com/docs/querying-collections/query-and-get) — query embeddings, results shape.
9. [Chroma: metadata filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering) — typed predicates and `$and` / `$or`.
10. [pgvector maintainers' README](https://github.com/pgvector/pgvector) — SQL operators, cosine distance, HNSW and hybrid SQL patterns.

## Grounded generation and agent tools

11. [OpenAI API: function calling](https://developers.openai.com/api/docs/guides/function-calling) — Responses `function_call`, `call_id` and `function_call_output` loop.
12. [OpenAI API: data controls](https://developers.openai.com/api/docs/guides/your-data) — `store`, retention and enterprise data-handling considerations.
13. [OpenAI API: models](https://platform.openai.com/docs/models) — model availability; use a model approved for the account.

## Security

14. [OWASP GenAI: LLM01 prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — untrusted retrieved text as attack surface.
15. [OWASP GenAI: LLM08 vector and embedding weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/) — access, poisoning, and RAG-specific retrieval weaknesses.
16. [OWASP GenAI: 2026 agentic incidents](https://genai.owasp.org/2026/10/08/genai-and-agentic-ai-exploit-roundup-q3-2026/) — recent context on tool and instruction attacks.

## Research and operational cautions

- This material intentionally avoids citing unverified performance figures or claiming that prompt-based grounding guarantees correctness.
- Model benchmark conclusions must be validated against current internal datasets, human-labelled evidence and deployment requirements.
- The SQL, Chroma filters and agent schemas are **teaching examples**; production authentication, scoped credentials and secure data lifecycle work remain outside this 150-minute course.
