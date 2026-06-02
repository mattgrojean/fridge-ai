import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

from config import (
    AZURE_CLIENT_ID,
    AZURE_STORAGE_ACCOUNT_NAME,
    AZURE_STORAGE_CONTAINER_NAME,
    PDF_LINK_TTL_MINUTES,
    SEARCH_ENDPOINT,
    SEARCH_INDEX_NAME,
)

SEARCH_DOC_URL_RE = re.compile(r"^mcp://searchindex/(?P<doc_id>[0-9a-f]{64})(?:[/?#].*)?$", re.IGNORECASE)
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
    return DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)


@lru_cache(maxsize=1)
def get_blob_service_client() -> BlobServiceClient:
    credential = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)
    return BlobServiceClient(
        account_url=f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
        credential=credential,
    )


@lru_cache(maxsize=1)
def get_search_http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))


def _get_search_service_config() -> tuple[str, str]:
    endpoint = SEARCH_ENDPOINT or _derive_search_endpoint(os.environ.get("FOUNDRY_SEARCH_MCP_ENDPOINT", ""))
    return endpoint.rstrip("/"), SEARCH_INDEX_NAME


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


def build_pdf_url(blob_name: str, page_number: int) -> str:
    blob_service_client = get_blob_service_client()
    now = datetime.now(timezone.utc)
    delegation_key = blob_service_client.get_user_delegation_key(
        key_start_time=now - timedelta(minutes=5),
        key_expiry_time=now + timedelta(minutes=PDF_LINK_TTL_MINUTES),
    )
    sas_token = generate_blob_sas(
        account_name=AZURE_STORAGE_ACCOUNT_NAME,
        container_name=AZURE_STORAGE_CONTAINER_NAME,
        blob_name=blob_name,
        user_delegation_key=delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=now + timedelta(minutes=PDF_LINK_TTL_MINUTES),
        start=now - timedelta(minutes=5),
    )
    encoded_blob_name = "/".join(quote(part) for part in blob_name.split("/"))
    return (
        f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/"
        f"{AZURE_STORAGE_CONTAINER_NAME}/{encoded_blob_name}?{sas_token}#page={page_number}"
    )


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
