from functools import lru_cache
from typing import Any, Dict, List

import openai
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from config import (
    AZURE_CLIENT_ID,
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX_NAME,
)


@lru_cache(maxsize=1)
def get_credential() -> DefaultAzureCredential:
    managed_identity_client_id = AZURE_CLIENT_ID or None
    return DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)


@lru_cache(maxsize=1)
def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=get_credential(),
    )


@lru_cache(maxsize=1)
def get_openai_client() -> openai.AzureOpenAI:
    credential = get_credential()
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    return openai.AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-12-01-preview",
    )


def search_manuals(query: str, top: int = 5) -> List[Dict[str, Any]]:
    openai_client = get_openai_client()
    search_client = get_search_client()

    embedding_response = openai_client.embeddings.create(
        model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        input=query,
    )
    embedding = embedding_response.data[0].embedding

    vector_query = VectorizedQuery(
        vector=embedding,
        k_nearest_neighbors=top,
        fields="content_vector",
    )

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="default",
        select=["content", "source_file", "page_number", "title"],
        top=top,
    )

    documents: List[Dict[str, Any]] = []
    for result in results:
        documents.append(
            {
                "content": result.get("content", ""),
                "source_file": result.get("source_file", "Unknown"),
                "page_number": int(result.get("page_number") or 0),
                "title": result.get("title", ""),
                "search_score": result.get("@search.score")
                or result.get("@search.reranker_score")
                or 0.0,
            }
        )

    return documents
