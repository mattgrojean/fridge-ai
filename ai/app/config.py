import os


def _get_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


AZURE_OPENAI_ENDPOINT = _get_required("AZURE_OPENAI_ENDPOINT")
AZURE_SEARCH_ENDPOINT = _get_required("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "manuals-index")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4-1-mini")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
)
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
ENTRA_CLIENT_ID = _get_required("ENTRA_CLIENT_ID")
ENTRA_TENANT_ID = _get_required("ENTRA_TENANT_ID")
APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ.get(
    "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
)
