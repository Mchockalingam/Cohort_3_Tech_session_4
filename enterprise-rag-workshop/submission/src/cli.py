"""Assignment CLI. Run from the workshop root:  python -m submission.src.cli <command> ...

Uses its own index (submission/.chroma) so the workshop's `.local_chroma` is never touched.
"""

import argparse
import json
import os

from src.chunking import create_chunks
from src.vector_store import ROLES

COMMANDS = ["audit", "reindex", "evaluate", "search", "acl-demo", "incident-packet", "answer",
            "agent", "offline-agent", "abstention", "adversarial", "chunk-experiment"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Northstar RAG assignment CLI")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--role", choices=sorted(ROLES), default="engineer")
    parser.add_argument("--question", "-q", default=None)
    parser.add_argument("--mode", choices=["dense", "keyword", "hybrid"], default="hybrid")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--budget", type=int, default=1200)
    args = parser.parse_args()

    from .incident import INCIDENT_QUESTION
    question = args.question or INCIDENT_QUESTION

    if args.command == "audit":  # A.1
        from .loader import catalog_audit
        rows = catalog_audit()
        cols = ["doc_id", "version", "status", "page", "allowed_roles", "doc_type",
                "classification", "trust", "effective_date", "indexed"]
        width = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
        print(" | ".join(c.ljust(width[c]) for c in cols))
        print("-+-".join("-" * width[c] for c in cols))
        for r in rows:
            print(" | ".join(str(r[c]).ljust(width[c]) for c in cols))
        print(f"{len(rows)} page records; {sum(not r['indexed'] for r in rows)} excluded from index (non-active)")
        return

    from src.embeddings import LocalEncoder
    encoder = LocalEncoder()

    if args.command == "chunk-experiment":  # B
        from .experiments import chunking_experiment
        print(json.dumps(chunking_experiment(encoder, k=args.k), indent=2))
        return
    if args.command == "adversarial":  # E.3
        from .experiments import adversarial_test
        answer_fn = None
        if os.getenv("OPENAI_API_KEY"):
            from src.generation import grounded_answer
            answer_fn = grounded_answer
        report = adversarial_test(encoder, answer_fn)
        if answer_fn is None:
            report["generation"] = "NOT RUN: no approved model key; retrieval/packet controls only"
        print(json.dumps(report, indent=2))
        return

    from .loader import load_catalog
    from .store import collection, reindex
    coll = collection()

    if args.command == "reindex":  # A.2 / A.3
        chunks = [c for d in load_catalog() for c in create_chunks(d, "headings", 550, 80)]
        print(json.dumps(reindex(coll, chunks, encoder)))
        print("Verified: store IDs == active catalog chunk IDs; no non-active records.")
        return
    if coll.count() == 0:
        raise SystemExit("Empty index: run `python -m submission.src.cli reindex` first")

    if args.command == "evaluate":  # E.2
        from .evaluate import retrieval_report
        print(json.dumps(retrieval_report(coll, encoder, args.mode, args.k), indent=2))
        return
    if args.command == "search":
        from .retrieve import SEARCH
        for i, h in enumerate(SEARCH[args.mode](coll, encoder, question, args.role, args.k), 1):
            print(f"{i}. {h.metadata['doc_id']} v{h.metadata['version']} ({h.method} {h.score:.4f}) "
                  + h.text[:160].replace("\n", " "))
        return
    if args.command == "acl-demo":  # C.2
        from .experiments import acl_demo
        for r in acl_demo(coll, encoder, args.k):
            flag = "RETRIEVED" if r["target_retrieved"] else "blocked"
            print(f"{r['target']:<13} role={r['role']:<9} mode={r['mode']:<8} {flag:<9} {r['retrieved']}")
        return
    if args.command in ("incident-packet", "answer"):  # C.3 / D.1
        from .incident import incident_packet
        packet, log = incident_packet(coll, encoder, args.role, args.budget)
        if args.command == "answer":
            from src.generation import citation_issues, grounded_answer
            from .safety import answer_policy_violations
            answer = grounded_answer(question, packet)  # requires an approved OPENAI_API_KEY
            print(answer)
            print("\nCITATION CHECK:", citation_issues(answer, set(packet.sources)) or "IDs valid")
            print("POLICY CHECK:", answer_policy_violations(answer) or "no bypass claims")
            return
        print(packet.text)
        print("\nSUB-QUERY LOG:\n" + json.dumps(log, indent=2))
        print("\nSOURCE MANIFEST:\n" + json.dumps(packet.manifest(), indent=2))
        print(f"\nQuarantined: {packet.quarantined}")
        print(f"Dropped (did not fit whole): {packet.dropped}")
        print(f"Evidence tokens={packet.token_count} (budget {args.budget})")
        return
    if args.command == "agent":  # D.2 with an approved model
        from .agent import run_agent
        answer, audit = run_agent(question, coll, encoder, role=args.role)
        print("ANSWER:\n" + answer + "\n\nAUDIT:\n" + json.dumps(audit, indent=2))
        return
    if args.command == "offline-agent":  # D.2 without a key
        from .agent import run_offline_agent
        # Two extra requests prove the guards: a write tool (denied) and a 6th call (over budget).
        answer, audit = run_offline_agent(question, coll, encoder, role=args.role,
                                          extra_calls=[("deploy_rollback", "roll back payments-api"),
                                                       ("search_postmortem", "pool incident review")])
        print(answer + "\n\nAUDIT:\n" + json.dumps(audit, indent=2))
        return
    if args.command == "abstention":  # E.2 abstention
        from .experiments import abstention_report
        print(json.dumps(abstention_report(coll, encoder), indent=2))
        return


if __name__ == "__main__":
    main()
