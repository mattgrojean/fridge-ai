import os


def _get_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


AZURE_AI_PROJECT_ENDPOINT = _get_required("AZURE_AI_PROJECT_ENDPOINT")
FOUNDRY_SEARCH_MCP_ENDPOINT = _get_required("FOUNDRY_SEARCH_MCP_ENDPOINT")
FOUNDRY_AGENT_NAME = os.environ.get("FOUNDRY_AGENT_NAME", "appliance-repair-agent")
FOUNDRY_KB_CONNECTION_NAME = os.environ.get("FOUNDRY_KB_CONNECTION_NAME", "manuals-kb-connection")
FOUNDRY_MODEL_DEPLOYMENT = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT", "gpt-5.4-mini")
SEARCH_ENDPOINT = os.environ.get(
    "SEARCH_ENDPOINT",
    FOUNDRY_SEARCH_MCP_ENDPOINT.split("/knowledgebases/")[0],
)
SEARCH_INDEX_NAME = os.environ.get("SEARCH_INDEX_NAME", "manuals-index")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_STORAGE_ACCOUNT_NAME = _get_required("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_CONTAINER_NAME = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "manuals")
PDF_LINK_TTL_MINUTES = int(os.environ.get("PDF_LINK_TTL_MINUTES", "10"))
ENTRA_CLIENT_ID = _get_required("ENTRA_CLIENT_ID")
ENTRA_API_SCOPE = os.environ.get("ENTRA_API_SCOPE", "")
ENTRA_TENANT_ID = _get_required("ENTRA_TENANT_ID")
ENTRA_ALLOWED_GROUP_ID = os.environ.get("ENTRA_ALLOWED_GROUP_ID", "")
APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ.get(
    "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
)
