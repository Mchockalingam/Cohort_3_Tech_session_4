"""Retrieval evaluation (Task E.2): same metrics as the original `src.evaluation`, run on the
extended gold set `submission/data/eval.jsonl`, through the fail-closed retrieval wrappers,
plus a forbidden-document leak count for every question."""

import json
import time
from pathlib import Path

from .retrieve import SEARCH

EVAL_FILE = Path(__file__).resolve().parents[1] / "data" / "eval.jsonl"


def retrieval_report(coll, encoder, mode: str = "hybrid", k: int = 5, eval_file: Path = EVAL_FILE) -> dict:
    search = SEARCH[mode]
    rows = []
    for line in Path(eval_file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        start = time.perf_counter()
        hits = search(coll, encoder, item["question"], item["role"], k)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        actual = [h.metadata["doc_id"] for h in hits]
        expected = set(item["expected_doc_ids"])
        # Never retrievable for ANY question: the retired version, and the restricted
        # security runbook for every non-security role.
        forbidden = set(item.get("forbidden_doc_ids", [])) | {"RUN-PAY-OLD"}
        if item["role"] != "security":
            forbidden.add("SEC-FRAUD-009")
        first = next((i for i, d in enumerate(actual, 1) if d in expected), None)
        rows.append({
            "id": item["id"], "category": item.get("category", "seed"), "role": item["role"],
            "expected": sorted(expected), "retrieved": actual, "should_abstain": item["should_abstain"],
            "hit_at_k": int(first is not None) if expected else None,
            "doc_recall_at_k": round(len(set(actual) & expected) / len(expected), 3) if expected else None,
            "rr": (round(1 / first, 3) if first else 0.0) if expected else None,
            "forbidden_leaks": sorted(set(actual) & forbidden),
            "latency_ms": latency_ms,
        })
    scored = [r for r in rows if r["expected"]]
    mean = lambda key: round(sum(r[key] for r in scored) / len(scored), 3) if scored else None
    return {
        "mode": mode, "k": k, "eval_file": "submission/data/eval.jsonl",
        "scored_question_count": len(scored),
        "mean_hit_at_k": mean("hit_at_k"), "mean_doc_recall_at_k": mean("doc_recall_at_k"),
        "mrr_at_k": mean("rr"),
        "forbidden_leak_count": sum(len(r["forbidden_leaks"]) for r in rows),
        "rows": rows,
        "note": "Unanswerable/role-denied rows are scored by the separate `abstention` command.",
    }
