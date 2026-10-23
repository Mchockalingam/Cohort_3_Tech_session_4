"""Run labs with `python -m src.cli <command> ...` from the repository root."""

import argparse
import json

from .chunking import create_chunks
from .loading import load_catalog
from .vector_store import DEFAULT_DB, ROLES


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise RAG workshop CLI")
    parser.add_argument("command", choices=["load", "chunk", "embed", "index", "search",
                                            "context", "answer", "agent", "evaluate"])
    parser.add_argument("--role", choices=sorted(ROLES), default="engineer")
    parser.add_argument("--question", "-q", default="How should we investigate a P1 payment API incident?")
    parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    parser.add_argument("--strategy", choices=["characters", "tokens", "sliding", "sentences",
                                                "paragraphs", "recursive", "headings", "semantic",
                                                "tables", "code"], default="headings")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--budget", type=int, default=1200, help="Evidence token budget")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Dedicated local Chroma directory")
    args = parser.parse_args()

    if args.command == "load":
        docs = load_catalog()
        for doc in docs:
            m = doc.metadata
            print(f"{m['doc_id']:<14} {m['status']:<8} page={m['page']} "
                  f"roles={','.join(m['allowed_roles']):<24} chars={len(doc.text)}")
        print(f"Loaded {len(docs)} synthetic document/page records")
        return

    if args.command == "chunk":
        docs = load_catalog()
        selected = next(doc for doc in docs if doc.metadata["doc_id"] == "RUN-PAY-101")
        callback = None
        if args.strategy == "semantic":
            from .embeddings import LocalEncoder
            callback = LocalEncoder().documents
        chunks = create_chunks(selected, strategy=args.strategy, size=430,
                               overlap=70, embed_sentences=callback)
        for chunk in chunks:
            print(f"\n{chunk.id} | {len(chunk.text)} chars | doc={chunk.metadata['doc_id']}")
            print(chunk.text[:450])
        print(f"\nTotal: {len(chunks)} chunks")
        return

    from .embeddings import LocalEncoder
    encoder = LocalEncoder()
    if args.command == "embed":
        import numpy as np
        vectors = encoder.documents([
            "Connection pool saturation causes payment timeouts.",
            "Database pool wait queues can cause checkout errors.",
            "The cafeteria opens at noon.",
        ])
        print(f"Model: {encoder.model_name}, dimension: {len(vectors[0])}")
        print("Cosine similarity (pool descriptions):", round(float(np.dot(vectors[0], vectors[1])), 3))
        print("Cosine similarity (pool/cafeteria):", round(float(np.dot(vectors[0], vectors[2])), 3))
        return

    from .vector_store import collection, upsert_chunks
    coll = collection(args.db)
    if args.command == "index":
        docs = [doc for doc in load_catalog() if doc.metadata["status"] == "active"]
        chunks = [chunk for doc in docs for chunk in create_chunks(doc, "headings", 550, 80)]
        added = upsert_chunks(coll, chunks, encoder)
        print(f"Upserted {added} active chunks; collection count={coll.count()}.")
        print("Retired material is excluded. Rebuild/rename the collection if versions or models change.")
        return

    from .retrieval import dense, hybrid, lexical
    fn = {"dense": dense, "keyword": lexical, "hybrid": hybrid}[args.mode]
    if args.command == "evaluate":
        from .evaluation import retrieval_report
        print(json.dumps(retrieval_report(coll, encoder, args.mode, args.k), indent=2))
        return
    if args.command == "agent":
        from .agent import run_agent
        answer, audit = run_agent(args.question, coll, encoder, role=args.role)
        print("ANSWER:\n" + answer + "\n\nAUDIT:\n" + json.dumps(audit, indent=2))
        return

    hits = fn(coll, encoder, args.question, args.role, args.k)
    if args.command == "search":
        if not hits:
            print("No authorised retrieval results. Have you run 'index'?")
        for i, hit in enumerate(hits, 1):
            m = hit.metadata
            print(f"{i}. {m['doc_id']} v{m['version']} ({hit.method} score={hit.score:.4f})")
            print("   " + hit.text[:200].replace("\n", " "))
        return

    from .context import build_packet
    packet = build_packet(hits, args.budget)
    if args.command == "context":
        print(packet.text or "NO AUTHORISED EVIDENCE")
        print(f"\nSources={list(packet.sources)}; approx evidence tokens={packet.token_count}")
        return
    from .generation import citation_issues, grounded_answer
    answer = grounded_answer(args.question, packet)
    print(answer)
    print("\nCITATION CHECK:", citation_issues(answer, set(packet.sources)) or "IDs valid")


if __name__ == "__main__":
    main()
