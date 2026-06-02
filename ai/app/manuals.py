import os
import re
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx

SEARCH_DOC_URL_RE = re.compile(r"^mcp://searchindex/(?P<doc_id>[0-9a-f]{64})(?:[/?#].*)?$", re.IGNORECASE)
DEFAULT_SEARCH_INDEX_NAME = "manuals-index"
SEARCH_API_VERSION = "2024-07-01"
SEARCH_TOKEN_SCOPE = "https://search.azure.com/.default"


def extract_search_document_id(annotation_url: str) -> str | None:
    match = SEARCH_DOC_URL_RE.match(annotation_url or "")
    return match.group("doc_id").lower() if match else None


def _derive_search_endpoint(foundry_search_mcp_endpoint: str) -> str:
    parsed = urlparse(foundry_search_mcp_endpoint or "")
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("FOUNDRY_SEARCH_MCP_ENDPOINT must include a valid search host")
    return f"{parsed.scheme}://{parsed.netloc}"


@lru_cache(maxsize=1)
def get_search_credential():
    from azure.identity import DefaultAzureCredential

    from config import AZURE_CLIENT_ID

    return DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)


@lru_cache(maxsize=1)
def get_search_http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))


def _get_search_service_config() -> tuple[str, str]:
    from config import FOUNDRY_SEARCH_MCP_ENDPOINT

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT") or _derive_search_endpoint(FOUNDRY_SEARCH_MCP_ENDPOINT)
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", DEFAULT_SEARCH_INDEX_NAME)
    return endpoint.rstrip("/"), index_name


def _build_lookup_url(endpoint: str, index_name: str, doc_id: str) -> str:
    quoted_index_name = quote(index_name, safe="")
    quoted_doc_id = quote(doc_id, safe="")
    return f"{endpoint}/indexes('{quoted_index_name}')/docs('{quoted_doc_id}')"


def load_search_document(doc_id: str) -> dict:
    endpoint, index_name = _get_search_service_config()
    access_token = get_search_credential().get_token(SEARCH_TOKEN_SCOPE)
    response = get_search_http_client().get(
        _build_lookup_url(endpoint, index_name, doc_id),
        params={
            "api-version": SEARCH_API_VERSION,
            "$select": "source_file,page_number,content",
        },
        headers={"Authorization": f"Bearer {access_token.token}"},
    )
    response.raise_for_status()
    return response.json()


def _normalize_source_file(source_file) -> str | None:
    if source_file is None:
        return None

    normalized = str(source_file).strip()
    return normalized or None


def _normalize_page_number(page_number) -> int | None:
    if isinstance(page_number, bool):
        return None

    try:
        normalized = int(page_number)
    except (TypeError, ValueError):
        return None

    return normalized if normalized >= 1 else None


def get_citation_metadata(doc_id: str) -> dict | None:
    document = load_search_document(doc_id)
    blob_name = _normalize_source_file(document.get("source_file"))
    page_number = _normalize_page_number(document.get("page_number"))

    if not blob_name or page_number is None:
        return None

    display_title = PurePosixPath(blob_name).name or blob_name

    return {
        "document_id": doc_id,
        "blob_name": blob_name,
        "display_title": display_title,
        "source_file": display_title,
        "page_number": page_number,
        "snippet": str(document.get("content") or ""),
        "content_snippet": str(document.get("content") or ""),
    }
