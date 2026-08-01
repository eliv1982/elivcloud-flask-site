"""Tests for the existing /chat endpoint's request validation and its
success path — the latter fully mocked (retrieval + OpenAI client), so this
file never makes a network call and never touches the real FAISS artifacts
under data/.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import tests  # noqa: E402,F401  (sys.path setup — see tests/__init__.py)
from tests.support import create_isolated_app


class ChatRouteValidationTests(unittest.TestCase):
    """26: /chat rejects missing/invalid JSON before ever reaching
    retrieval or OpenAI — none of these should call either."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_non_json_request_rejected(self):
        with patch("rag_index.search_knowledge_base") as mock_search:
            response = self.client.post(
                "/chat", data="not json", content_type="text/plain"
            )
        self.assertEqual(response.status_code, 400)
        mock_search.assert_not_called()

    def test_missing_message_field_rejected(self):
        with patch("rag_index.search_knowledge_base") as mock_search:
            response = self.client.post("/chat", json={"history": []})
        self.assertEqual(response.status_code, 400)
        mock_search.assert_not_called()

    def test_blank_message_rejected(self):
        with patch("rag_index.search_knowledge_base") as mock_search:
            response = self.client.post("/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 400)
        mock_search.assert_not_called()

    def test_oversized_message_rejected(self):
        with patch("rag_index.search_knowledge_base") as mock_search:
            response = self.client.post("/chat", json={"message": "x" * 3000})
        self.assertEqual(response.status_code, 400)
        mock_search.assert_not_called()


class ChatRouteMockedSuccessTests(unittest.TestCase):
    """27: one successful /chat round trip using mocks only — mocked
    retrieval, mocked OpenAI client/result, no network call, verifying the
    endpoint still returns the expected {answer, sources} JSON shape."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_isolated_app()
        cls.client = cls.app.test_client()

    def test_chat_success_path_with_mocks_only(self):
        fake_rag_results = [
            {
                "score": 0.87654,
                "question": "What is ElivCloud?",
                "answer": "A placeholder knowledge-base answer.",
                "source": "site.json",
                "kind": "faq",
            }
        ]

        fake_message = MagicMock()
        fake_message.content = "Mocked assistant answer."
        fake_choice = MagicMock()
        fake_choice.message = fake_message
        fake_completion = MagicMock()
        fake_completion.choices = [fake_choice]

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = fake_completion

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-not-real"}),
            patch("rag_index.search_knowledge_base", return_value=fake_rag_results) as mock_search,
            patch("elivcloud.OpenAI", return_value=mock_client_instance) as mock_openai_cls,
        ):
            response = self.client.post(
                "/chat", json={"message": "What is ElivCloud?", "history": []}
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("answer", data)
        self.assertIn("sources", data)
        self.assertEqual(data["answer"], "Mocked assistant answer.")
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(data["sources"][0]["source"], "site.json")

        mock_search.assert_called_once()
        mock_openai_cls.assert_called_once()
        mock_client_instance.chat.completions.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
