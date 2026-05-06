import unittest

from backend import retrieval


class RetrievalHelperTests(unittest.TestCase):
    def test_dedupe_results_uses_doc_page_and_text(self):
        results = [
            {"doc_id": "a", "page": 1, "text": "same", "score": 0.9},
            {"doc_id": "a", "page": 1, "text": "same", "score": 0.8},
            {"doc_id": "a", "page": 2, "text": "same", "score": 0.7},
            {"doc_id": "b", "page": 1, "text": "same", "score": 0.6},
        ]

        deduped = retrieval._dedupe_results(results)

        self.assertEqual(len(deduped), 3)
        self.assertEqual(deduped[0]["score"], 0.9)
        self.assertEqual(deduped[1]["page"], 2)
        self.assertEqual(deduped[2]["doc_id"], "b")


if __name__ == "__main__":
    unittest.main()
