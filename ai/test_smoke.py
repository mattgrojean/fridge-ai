"""Basic smoke tests for the Appliance AI backend."""
import os
import sys
import unittest

# Put the app directory on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

# Set required env vars before any app imports
os.environ.setdefault("AZURE_AI_PROJECT_ENDPOINT", "https://test/endpoint")
os.environ.setdefault("FOUNDRY_SEARCH_MCP_ENDPOINT", "https://test/kb/mcp")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "teststore")
os.environ.setdefault("ENTRA_CLIENT_ID", "dev-skip-auth")
os.environ.setdefault("ENTRA_TENANT_ID", "test-tenant")


class TestConfig(unittest.TestCase):
    def test_required_vars_present(self):
        from config import (
            AZURE_AI_PROJECT_ENDPOINT,
            AZURE_STORAGE_ACCOUNT_NAME,
            ENTRA_CLIENT_ID,
            ENTRA_TENANT_ID,
            FOUNDRY_SEARCH_MCP_ENDPOINT,
        )
        self.assertTrue(AZURE_AI_PROJECT_ENDPOINT)
        self.assertTrue(FOUNDRY_SEARCH_MCP_ENDPOINT)
        self.assertTrue(AZURE_STORAGE_ACCOUNT_NAME)
        self.assertEqual(ENTRA_CLIENT_ID, "dev-skip-auth")
        self.assertTrue(ENTRA_TENANT_ID)

    def test_optional_vars_have_defaults(self):
        from config import (
            FOUNDRY_AGENT_NAME,
            FOUNDRY_KB_CONNECTION_NAME,
            SEARCH_INDEX_NAME,
            AZURE_STORAGE_CONTAINER_NAME,
            PDF_LINK_TTL_MINUTES,
        )
        self.assertEqual(FOUNDRY_AGENT_NAME, "appliance-repair-agent")
        self.assertEqual(FOUNDRY_KB_CONNECTION_NAME, "manuals-kb-connection")
        self.assertEqual(SEARCH_INDEX_NAME, "manuals-index")
        self.assertEqual(AZURE_STORAGE_CONTAINER_NAME, "manuals")
        self.assertIsInstance(PDF_LINK_TTL_MINUTES, int)


class TestModels(unittest.TestCase):
    def test_chat_request(self):
        from models import ChatRequest
        r = ChatRequest(message="test")
        self.assertEqual(r.message, "test")
        self.assertIsNone(r.conversation_id)

    def test_chat_response(self):
        from models import ChatResponse
        r = ChatResponse(answer="hello", citations=[], conversation_id="abc", message_index=0)
        self.assertEqual(r.answer, "hello")
        self.assertEqual(r.citations, [])
        self.assertEqual(r.conversation_id, "abc")
        self.assertEqual(r.message_index, 0)

    def test_feedback_request(self):
        from models import FeedbackRequest
        f = FeedbackRequest(conversation_id="abc", message_index=0, rating="up")
        self.assertEqual(f.rating, "up")

    def test_citation(self):
        from models import Citation
        c = Citation(
            document_id="abc123",
            blob_name="manuals/test.pdf",
            display_title="test.pdf",
            source_file="test.pdf",
            page_number=5,
            snippet="some text",
            content_snippet="some text",
        )
        self.assertEqual(c.document_id, "abc123")
        self.assertEqual(c.page_number, 5)


class TestManuals(unittest.TestCase):
    def test_extract_search_document_id(self):
        from manuals import extract_search_document_id
        valid = "mcp://searchindex/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        doc_id = extract_search_document_id(valid)
        self.assertEqual(doc_id, "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")

    def test_extract_search_document_id_invalid(self):
        from manuals import extract_search_document_id
        self.assertIsNone(extract_search_document_id(""))
        self.assertIsNone(extract_search_document_id("not-a-url"))
        self.assertIsNone(extract_search_document_id("https://example.com/doc"))


class TestChat(unittest.TestCase):
    def test_strip_citation_markers(self):
        from chat import _strip_citation_markers
        self.assertEqual(_strip_citation_markers("Hello world"), "Hello world")
        # Citation markers should be stripped
        text = "Check the drain pump 【source†source】 for details"
        result = _strip_citation_markers(text)
        self.assertNotIn("【", result)
        self.assertIn("Check the drain pump", result)


class TestAuth(unittest.TestCase):
    def test_dev_skip_returns_mock_user(self):
        from auth import _mock_user
        user = _mock_user()
        self.assertEqual(user["name"], "Development User")
        self.assertEqual(user["oid"], "dev-user")

    def test_extract_bearer(self):
        from auth import _extract_bearer_token
        token = _extract_bearer_token("Bearer abc.def.ghi")
        self.assertEqual(token, "abc.def.ghi")

    def test_extract_bearer_missing(self):
        from auth import _extract_bearer_token
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _extract_bearer_token(None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
