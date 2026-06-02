from functools import lru_cache

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential

from config import (
    AZURE_AI_PROJECT_ENDPOINT,
    AZURE_CLIENT_ID,
    FOUNDRY_AGENT_NAME,
    FOUNDRY_KB_CONNECTION_NAME,
    FOUNDRY_MODEL_DEPLOYMENT,
    FOUNDRY_SEARCH_MCP_ENDPOINT,
)

AGENT_INSTRUCTIONS = (
    "You are a knowledgeable appliance repair assistant for field technicians. "
    "You MUST use the knowledge base tool to answer all questions — never answer from your own training data. "
    "If the knowledge base does not contain the answer, respond with: 'I don't know.' "
    "Always cite your sources using the annotation format provided by the tool. "
    "Be concise and practical — technicians need quick answers in the field."
)


@lru_cache(maxsize=1)
def get_project_client() -> AIProjectClient:
    cred = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)
    return AIProjectClient(endpoint=AZURE_AI_PROJECT_ENDPOINT, credential=cred)


@lru_cache(maxsize=1)
def get_openai_client():
    return get_project_client().get_openai_client()


@lru_cache(maxsize=1)
def get_or_create_agent():
    """Creates a new agent version on first call, then caches it for the process lifetime."""
    client = get_project_client()
    mcp_tool = MCPTool(
        server_label="knowledge-base",
        server_url=FOUNDRY_SEARCH_MCP_ENDPOINT,
        require_approval="never",
        allowed_tools=["knowledge_base_retrieve"],
        project_connection_id=FOUNDRY_KB_CONNECTION_NAME,
    )
    return client.agents.create_version(
        agent_name=FOUNDRY_AGENT_NAME,
        definition=PromptAgentDefinition(
            model=FOUNDRY_MODEL_DEPLOYMENT,
            instructions=AGENT_INSTRUCTIONS,
            tools=[mcp_tool],
        ),
    )
