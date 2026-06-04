import logging
import re
from typing import List, Optional, Tuple

from manuals import extract_search_document_id, get_citation_metadata
from models import Citation

CITATION_MARKER_RE = re.compile(r"\s*【[^】]+†source】")
logger = logging.getLogger(__name__)


def _strip_citation_markers(answer_text: str) -> str:
    return CITATION_MARKER_RE.sub("", answer_text or "").strip()


def _parse_citations(output_items) -> List[Citation]:
    """Extract structured citations from Foundry response output annotations."""
    citations: List[Citation] = []
    seen: set[str] = set()

    for item in output_items or []:
        for block in getattr(item, "content", None) or []:
            for annotation in getattr(block, "annotations", None) or []:
                doc_id = extract_search_document_id(getattr(annotation, "url", ""))
                if not doc_id or doc_id in seen:
                    continue

                seen.add(doc_id)
                try:
                    citation_metadata = get_citation_metadata(doc_id)
                    if citation_metadata:
                        citations.append(Citation(**citation_metadata))
                except Exception:
                    logger.warning("Skipping citation hydration for document %s", doc_id, exc_info=True)
    return citations


def delete_foundry_conversation(foundry_conversation_id: str) -> None:
    """Delete a Foundry conversation, ignoring errors if it is already gone."""
    try:
        from search import get_openai_client

        client = get_openai_client()
        client.conversations.delete(conversation_id=foundry_conversation_id)
    except Exception:
        logger.debug(
            "Could not delete Foundry conversation %s", foundry_conversation_id, exc_info=True
        )


def generate_response(
    user_message: str,
    foundry_conversation_id: Optional[str] = None,
) -> Tuple[str, List[Citation], str]:
    """
    Calls the Foundry Agent with the user message, managing conversation state.

    Returns (answer_text, citations, foundry_conversation_id).
    """
    from search import get_openai_client, get_or_create_agent

    agent = get_or_create_agent()
    openai_client = get_openai_client()

    if foundry_conversation_id is None:
        conversation = openai_client.conversations.create()
        foundry_conversation_id = conversation.id

    response = openai_client.responses.create(
        conversation=foundry_conversation_id,
        input=user_message,
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    )

    answer_text = _strip_citation_markers((response.output_text or "").strip())
    if not answer_text:
        answer_text = "I couldn't find enough information in the manuals to answer that."

    citations = _parse_citations(getattr(response, "output", None))

    return answer_text, citations, foundry_conversation_id