import os
import re
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import urlparse

SEARCH_DOC_URL_RE = re.compile(r"^mcp://searchindex/(?P<doc_id>[0-9a-f]{64})(?:[/?#].*)?$", re.IGNORECASE)
DEFAULT_SEARCH_INDEX_NAME = "manuals-index"


def extract_search_document_id(annotation_url: str) -> str | None:
    match = SEARCH_DOC_URL_RE.match(annotation_url or "")
    return match.group("doc_id").lower() if match else None


def _derive_search_endpoint(foundry_search_mcp_endpoint: str) -> str:
    parsed = urlparse(foundry_search_mcp_endpoint or "")
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("FOUNDRY_SEARCH_MCP_ENDPOINT must include a valid search host")
    return f"{parsed.scheme}://{parsed.netloc}"


@lru_cache(maxsize=1)
def get_search_client():
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient

    from config import AZURE_CLIENT_ID, FOUNDRY_SEARCH_MCP_ENDPOINT

    credential = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT") or _derive_search_endpoint(FOUNDRY_SEARCH_MCP_ENDPOINT)
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", DEFAULT_SEARCH_INDEX_NAME)
    return SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)


def load_search_document(doc_id: str) -> dict:
    return dict(get_search_client().get_document(key=doc_id))


def get_citation_metadata(doc_id: str) -> dict:
    document = load_search_document(doc_id)
    blob_name = str(document.get("source_file") or document.get("title") or doc_id)
    display_title = PurePosixPath(blob_name).name or blob_name

    try:
        page_number = int(document.get("page_number") or 0)
    except (TypeError, ValueError):
        page_number = 0

    return {
        "document_id": doc_id,
        "blob_name": blob_name,
        "display_title": display_title,
        "page_number": page_number,
        "snippet": str(document.get("content") or ""),
    }