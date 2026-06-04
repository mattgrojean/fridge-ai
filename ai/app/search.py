import hashlib
import json
import logging
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

logger = logging.getLogger(__name__)

AGENT_INSTRUCTIONS = (
    "You are a knowledgeable appliance repair assistant for field technicians. "
    "You MUST use the knowledge base tool to answer all questions — never answer from your own training data. "
    "If the knowledge base does not contain the answer, respond with a friendly message explaining "
    "that the service manuals don't cover that topic, and suggest the technician ask a question "
    "about diagnostics, repair procedures, parts, or troubleshooting instead. "
    "For casual greetings like 'hello' or 'hi', respond warmly and briefly without invoking the tool. "
    "Always cite your sources using the annotation format provided by the tool. "
    "Be concise and practical — technicians need quick answers in the field."
)

_DEFINITION_HASH_KEY = "definition_hash"


def _build_definition_hash() -> str:
    """SHA-256 of the canonical agent definition so we can detect changes."""
    canonical = {
        "model": FOUNDRY_MODEL_DEPLOYMENT,
        "instructions": AGENT_INSTRUCTIONS,
        "mcp_endpoint": FOUNDRY_SEARCH_MCP_ENDPOINT,
        "kb_connection": FOUNDRY_KB_CONNECTION_NAME,
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


@lru_cache(maxsize=1)
def get_project_client() -> AIProjectClient:
    cred = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)
    return AIProjectClient(endpoint=AZURE_AI_PROJECT_ENDPOINT, credential=cred)


@lru_cache(maxsize=1)
def get_openai_client():
    return get_project_client().get_openai_client()


@lru_cache(maxsize=1)
def get_or_create_agent():
    """Return the agent version matching the current definition.

    On each deploy the function hashes the agent definition (instructions,
    model, tools, etc.).  If an existing version already carries the same
    hash it is reused so that process restarts do not create duplicate
    versions.  When the definition changes a fresh version is created
    automatically.
    """
    client = get_project_client()
    current_hash = _build_definition_hash()

    # Check whether the latest version already matches the current definition
    existing = list(client.agents.list_versions(
        agent_name=FOUNDRY_AGENT_NAME,
        limit=1,
        order="desc",
    ))
    if existing:
        latest = existing[0]
        stored_hash = (latest.metadata or {}).get(_DEFINITION_HASH_KEY)
        if stored_hash == current_hash:
            logger.info("Reusing agent version %s (hash %s…)", latest.version, current_hash[:12])
            return latest
        logger.info("Definition changed — creating new agent version (was %s…, now %s…)",
                     (stored_hash or "none")[:12], current_hash[:12])

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
        metadata={_DEFINITION_HASH_KEY: current_hash},
    )
