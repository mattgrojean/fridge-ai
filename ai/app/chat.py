from typing import List, Optional, Tuple

from models import Citation
from search import get_openai_client, get_or_create_agent


def _parse_citations(output_items) -> List[Citation]:
    """Extract structured citations from Foundry response output annotations."""
    citations: List[Citation] = []
    seen: set = set()

    for item in output_items or []:
        content_blocks = getattr(item, "content", None) or []
        for block in content_blocks:
            for annotation in getattr(block, "annotations", None) or []:
                url = getattr(annotation, "url", "") or ""
                title = getattr(annotation, "title", "") or url
                key = (title, url)
                if key not in seen:
                    seen.add(key)
                    citations.append(
                        Citation(
                            source_file=title or "Unknown",
                            page_number=0,
                            content_snippet=url,
                        )
                    )

    return citations


def generate_response(
    user_message: str,
    foundry_conversation_id: Optional[str] = None,
) -> Tuple[str, List[Citation], str]:
    """
    Calls the Foundry Agent with the user message, managing conversation state.

    Returns (answer_text, citations, foundry_conversation_id).
    """
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

    answer_text = (response.output_text or "").strip()
    if not answer_text:
        answer_text = "I couldn't find enough information in the manuals to answer that."

    citations = _parse_citations(getattr(response, "output", None))

    return answer_text, citations, foundry_conversation_id

