"""Offline, dependency-light tests. These do not download an embedding model."""

import unittest

from src.chunking import (code_fence_aware, create_chunks, fixed_char, markdown_headings,
                          parent_child, recursive, semantic, sentence_window, table_aware)
from src.generation import citation_issues
from src.loading import load_catalog
from src.models import SearchHit, SourceDocument
from src.retrieval import dense, reciprocal_rank_fusion
from src.vector_store import authorization_filter


class LoadingTests(unittest.TestCase):
    def test_catalog_has_roles_and_retired_document(self):
        docs = load_catalog()
        self.assertEqual(len(docs), 7)
        self.assertTrue(all(d.metadata["source_path"].startswith("data/") for d in docs))
        self.assertIn("retired", {d.metadata["status"] for d in docs})

    def test_authorization_filter_must_include_tenant_status_role(self):
        conditions = authorization_filter("engineer", "runbook")["$and"]
        self.assertIn({"role_engineer": {"$eq": True}}, conditions)
        self.assertIn({"status": {"$eq": "active"}}, conditions)
        self.assertIn({"tenant_id": {"$eq": "northstar-demo"}}, conditions)
        with self.assertRaises(ValueError):
            authorization_filter("admin")


class ChunkingTests(unittest.TestCase):
    def setUp(self):
        self.doc = SourceDocument("# Topic\n\nFirst sentence. Second sentence.\n\n## More\n\nThird sentence.",
                                  {"doc_id": "D1", "version": "1", "page": 1,
                                   "status": "active", "allowed_roles": ["engineer"]})

    def test_fixed_char_overlap(self):
        self.assertEqual(fixed_char("abcdefghij", 5, 2), ["abcde", "defgh", "ghij", "j"])
        with self.assertRaises(ValueError):
            fixed_char("abc", 10, 10)

    def test_structural_and_parent_child(self):
        self.assertGreaterEqual(len(markdown_headings(self.doc.text, 45, 5)), 2)
        self.assertTrue(all(chunk.id for chunk in create_chunks(self.doc, "headings", 50, 5)))
        children, lookup = parent_child(self.doc, 45, 25)
        self.assertGreater(len(children), 0)
        self.assertTrue(all(c.metadata["parent_id"] in lookup for c in children))

    def test_recursive_and_sentence_windows(self):
        self.assertGreater(len(recursive(self.doc.text, 35, 5)), 1)
        self.assertTrue(sentence_window("Alpha one. Beta two. Gamma three.", 2, 1))

    def test_semantic_callback(self):
        fake_encoder = lambda sentences: [[1, 0], [0, 1], [1, 0]][:len(sentences)]
        groups = semantic("Alpha one. Beta two. Gamma three.", fake_encoder,
                          threshold=0.5, max_chars=60)
        self.assertEqual(len(groups), 3)

    def test_table_and_code_preserved(self):
        table = "| Metric | Target |\n|---|---|\n| p95 | 100ms |"
        self.assertIn(table, table_aware("Intro\n\n" + table, 100))
        self.assertIn("```python\nprint(1)\n```", code_fence_aware("Hi\n```python\nprint(1)\n```", 100))


class EvidenceTests(unittest.TestCase):
    def test_rrf_rank_based(self):
        a = SearchHit("a", "A", {"doc_id": "A"}, 0.5)
        b = SearchHit("b", "B", {"doc_id": "B"}, 50)
        result = reciprocal_rank_fusion([[a, b], [b, a]], limit=2)
        self.assertEqual({hit.id for hit in result}, {"a", "b"})
        self.assertEqual(result[0].method, "rrf")

    def test_citation_whitelist(self):
        self.assertEqual(citation_issues("Use [S1].", {"S1"}), [])
        self.assertTrue(citation_issues("Use [S99].", {"S1"}))

    def test_dense_passes_acl_predicates_into_store_query(self):
        class FakeEncoder:
            def query(self, text):
                return [1.0, 0.0]

        class FakeCollection:
            def count(self):
                return 1

            def query(self, **kwargs):
                self.seen_where = kwargs["where"]
                return {"ids": [["example"]], "documents": [["approved text"]],
                        "metadatas": [[{"doc_id": "D1"}]], "distances": [[0.2]]}

        coll = FakeCollection()
        results = dense(coll, FakeEncoder(), "approval", role="engineer", doc_type="policy")
        self.assertIn({"role_engineer": {"$eq": True}}, coll.seen_where["$and"])
        self.assertIn({"doc_type": {"$eq": "policy"}}, coll.seen_where["$and"])
        self.assertAlmostEqual(results[0].score, 0.8)


if __name__ == "__main__":
    unittest.main()
