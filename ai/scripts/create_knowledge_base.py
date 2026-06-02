"""
Setup script: creates the Foundry IQ knowledge source, knowledge base, and project
connection on top of the existing Azure AI Search index.

Run this once after `terraform apply` and before running the app:

    python create_knowledge_base.py \
        --search-endpoint https://<name>.search.windows.net \
        --ai-services-endpoint https://<name>.cognitiveservices.azure.com/ \
        --project-resource-id /subscriptions/.../projects/appliance-ai-project \
        --model-deployment gpt-4-1-mini \
        --model-name gpt-4.1-mini

Prerequisites (RBAC):
  - Caller needs Search Service Contributor + Search Index Data Contributor on the
    Azure AI Search service.
  - Caller needs Foundry Project Manager on the AI Services account (to create the
    project connection).
"""

from __future__ import annotations

import argparse

import requests
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

SEARCH_API_VERSION = "2025-11-01-preview"
ML_CONNECTION_API_VERSION = "2025-10-01-preview"

KNOWLEDGE_SOURCE_NAME = "manuals-ks"
KNOWLEDGE_BASE_NAME = "manuals-kb"
PROJECT_CONNECTION_NAME = "manuals-kb-connection"
INDEX_NAME = "manuals-index"
SEMANTIC_CONFIG_NAME = "default"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Foundry IQ knowledge source, knowledge base, and project connection."
    )
    parser.add_argument(
        "--search-endpoint",
        required=True,
        help="Azure AI Search service URL, e.g. https://<name>.search.windows.net",
    )
    parser.add_argument(
        "--ai-services-endpoint",
        required=True,
        help="AI Services account endpoint URL used as the LLM provider for query planning",
    )
    parser.add_argument(
        "--project-resource-id",
        required=True,
        help=(
            "ARM resource ID of the Foundry project, e.g. "
            "/subscriptions/{sub}/resourceGroups/{rg}/providers/"
            "Microsoft.MachineLearningServices/workspaces/{account}/projects/{project}"
        ),
    )
    parser.add_argument(
        "--model-deployment",
        default="gpt-4-1-mini",
        help="Name of the GPT deployment used for query planning",
    )
    parser.add_argument(
        "--model-name",
        default=None,
        help="Foundry knowledge base model name. Defaults to the deployment name.",
    )
    return parser.parse_args()


def create_knowledge_source(
    search_endpoint: str,
    search_headers: dict,
) -> None:
    url = (
        f"{search_endpoint.rstrip('/')}/knowledgesources"
        f"/{KNOWLEDGE_SOURCE_NAME}?api-version={SEARCH_API_VERSION}"
    )
    payload = {
        "name": KNOWLEDGE_SOURCE_NAME,
        "kind": "searchIndex",
        "description": "Appliance service manuals indexed for agentic retrieval.",
        "searchIndexParameters": {
            "searchIndexName": INDEX_NAME,
            "semanticConfigurationName": SEMANTIC_CONFIG_NAME,
            "sourceDataFields": [
                {"name": "content"},
                {"name": "title"},
                {"name": "source_file"},
                {"name": "page_number"},
            ],
        },
    }
    resp = requests.put(url, headers=search_headers, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Knowledge source '{KNOWLEDGE_SOURCE_NAME}' ready.")


def create_knowledge_base(
    search_endpoint: str,
    search_headers: dict,
    ai_services_endpoint: str,
    model_deployment: str,
    model_name: str,
) -> None:
    url = (
        f"{search_endpoint.rstrip('/')}/knowledgebases"
        f"/{KNOWLEDGE_BASE_NAME}?api-version={SEARCH_API_VERSION}"
    )
    payload = {
        "name": KNOWLEDGE_BASE_NAME,
        "description": "Appliance service manuals knowledge base for Foundry IQ.",
        "knowledgeSources": [{"name": KNOWLEDGE_SOURCE_NAME}],
        "models": [
            {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": ai_services_endpoint.rstrip("/"),
                    "deploymentId": model_deployment,
                    "modelName": model_name,
                },
            }
        ],
        "retrievalReasoningEffort": {"kind": "low"},
    }
    resp = requests.put(url, headers=search_headers, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Knowledge base '{KNOWLEDGE_BASE_NAME}' ready.")


def create_project_connection(
    project_resource_id: str,
    search_endpoint: str,
    management_headers: dict,
) -> None:
    mcp_endpoint = (
        f"{search_endpoint.rstrip('/')}/knowledgebases"
        f"/{KNOWLEDGE_BASE_NAME}/mcp?api-version={SEARCH_API_VERSION}"
    )
    url = (
        f"https://management.azure.com{project_resource_id}"
        f"/connections/{PROJECT_CONNECTION_NAME}?api-version={ML_CONNECTION_API_VERSION}"
    )
    payload = {
        "name": PROJECT_CONNECTION_NAME,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": mcp_endpoint,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        },
    }
    resp = requests.put(url, headers=management_headers, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Project connection '{PROJECT_CONNECTION_NAME}' ready.")
    print(f"  MCP endpoint: {mcp_endpoint}")


def main() -> None:
    args = parse_args()
    credential = DefaultAzureCredential()

    search_token_provider = get_bearer_token_provider(
        credential, "https://search.azure.com/.default"
    )
    management_token_provider = get_bearer_token_provider(
        credential, "https://management.azure.com/.default"
    )

    search_headers = {
        "Authorization": f"Bearer {search_token_provider()}",
        "Content-Type": "application/json",
    }
    management_headers = {
        "Authorization": f"Bearer {management_token_provider()}",
        "Content-Type": "application/json",
    }

    print("Step 1/3: Creating knowledge source...")
    create_knowledge_source(args.search_endpoint, search_headers)

    print("Step 2/3: Creating knowledge base...")
    create_knowledge_base(
        args.search_endpoint,
        search_headers,
        args.ai_services_endpoint,
        args.model_deployment,
        args.model_name or args.model_deployment,
    )

    print("Step 3/3: Creating project connection...")
    create_project_connection(
        args.project_resource_id,
        args.search_endpoint,
        management_headers,
    )

    print("\nDone! Run the app or ingest manuals next.")
    print(
        f"  Agent will use connection: {PROJECT_CONNECTION_NAME}\n"
        f"  Knowledge base:            {KNOWLEDGE_BASE_NAME}\n"
        f"  Knowledge source:          {KNOWLEDGE_SOURCE_NAME}"
    )


if __name__ == "__main__":
    main()
