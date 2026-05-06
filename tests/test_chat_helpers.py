import unittest

from backend import chat


class ChatHelperTests(unittest.TestCase):
    def test_parse_rerank_indices_accepts_json_array_only(self):
        self.assertEqual(chat._parse_rerank_indices("[1, 3, 99]", limit=4), [1, 3])

    def test_parse_rerank_indices_returns_empty_for_invalid_json(self):
        self.assertEqual(chat._parse_rerank_indices("none", limit=4), [])

    def test_not_found_answer_has_no_citations(self):
        chunks = [{"filename": "AI_ACT.pdf", "page": 1, "text": "x"}]
        self.assertEqual(chat._citations_for_answer(chat.NOT_FOUND_ANSWER, chunks), [])

    def test_citations_follow_referenced_source_markers_only(self):
        chunks = [
            {"filename": "AI_ACT.pdf", "page": 1, "text": "a"},
            {"filename": "AI_ACT.pdf", "page": 360, "text": "b"},
            {"filename": "CV.pdf", "page": 1, "text": "c"},
        ]

        self.assertEqual(
            chat._citations_for_answer("The answer is here. (Source 2)", chunks),
            [{"filename": "AI_ACT.pdf", "page": 360}],
        )

    def test_missing_source_marker_has_no_citations(self):
        chunks = [{"filename": "AI_ACT.pdf", "page": 1, "text": "x"}]
        self.assertEqual(chat._citations_for_answer("The answer is here.", chunks), [])


if __name__ == "__main__":
    unittest.main()
