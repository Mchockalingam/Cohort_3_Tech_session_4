"""Evidence-retrieval evaluation. Not an automated proof of answer faithfulness."""

import json
import time
from pathlib import Path

from .loading import PROJECT_ROOT
from .retrieval import dense, hybrid, lexical


def retrieval_report(coll, encoder, mode: str = "hybrid", k: int = 5,
                     eval_file: Path = PROJECT_ROOT / "data" / "eval.jsonl") -> dict:
    search_fn = {"dense": dense, "keyword": lexical, "hybrid": hybrid}[mode]
    rows = []
    for line in Path(eval_file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        start = time.perf_counter()
        hits = search_fn(coll, encoder, item["question"], item["role"], k)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        actual_ids = [hit.metadata["doc_id"] for hit in hits]
        expected = set(item["expected_doc_ids"])
        first_rank = next((i for i, doc_id in enumerate(actual_ids, 1) if doc_id in expected), None)
        rows.append({
            "id": item["id"], "role": item["role"], "expected": sorted(expected),
            "retrieved": actual_ids, "should_abstain": item["should_abstain"],
            "hit_at_k": int(first_rank is not None) if expected else None,
            "doc_recall_at_k": round(len(set(actual_ids) & expected) / len(expected), 3)
            if expected else None,
            "rr": round(1 / first_rank, 3) if first_rank else 0.0 if expected else None,
            "latency_ms": latency_ms,
        })
    scored = [row for row in rows if row["expected"]]
    return {
        "mode": mode, "k": k, "scored_question_count": len(scored),
        "mean_hit_at_k": round(sum(r["hit_at_k"] for r in scored) / len(scored), 3)
        if scored else None,
        "mean_doc_recall_at_k": round(sum(r["doc_recall_at_k"] for r in scored) / len(scored), 3)
        if scored else None,
        "mrr_at_k": round(sum(r["rr"] for r in scored) / len(scored), 3)
        if scored else None,
        "rows": rows,
        "note": "Cases with no expected sources require a separate answer-level abstention test."
    }
