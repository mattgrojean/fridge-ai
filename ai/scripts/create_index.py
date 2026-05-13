from __future__ import annotations

import argparse

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or update the Azure AI Search index for appliance manuals."
    )
    parser.add_argument("--search-endpoint", required=True, help="Azure AI Search endpoint URL")
    parser.add_argument("--index-name", default="manuals-index", help="Search index name")
    return parser.parse_args()


def build_index(index_name: str) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            analyzer_name="en.microsoft",
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="default-profile",
        ),
        SimpleField(
            name="source_file",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
        SearchableField(name="title", type=SearchFieldDataType.String),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="default-profile",
                algorithm_configuration_name="default-hnsw",
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                ),
            )
        ],
        default_configuration_name="default",
    )

    return SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )


def main() -> None:
    args = parse_args()
    credential = DefaultAzureCredential()
    client = SearchIndexClient(
        endpoint=args.search_endpoint.rstrip("/"),
        credential=credential,
    )

    index = build_index(args.index_name)
    created_index = client.create_or_update_index(index)
    print(
        f"Search index '{created_index.name}' is ready with {len(created_index.fields)} fields."
    )


if __name__ == "__main__":
    main()
