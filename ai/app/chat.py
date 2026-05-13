from typing import Dict, List, Tuple

from config import AZURE_OPENAI_CHAT_DEPLOYMENT
from models import Citation
from search import get_openai_client, search_manuals

SYSTEM_PROMPT = (
    "You are a knowledgeable appliance repair assistant for field technicians. "
    "Answer questions using ONLY the provided context from service manuals. "
    "If the context doesn't contain the answer, say so honestly. "
    "Always cite your sources using [Source: filename, Page X] format. "
    "Be concise and practical — technicians need quick answers in the field."
)


def _build_context(search_results: List[Dict]) -> str:
    if not search_results:
        return "No relevant service manual content was retrieved."

    blocks: List[str] = []
    for index, result in enumerate(search_results, start=1):
        source_file = result.get("source_file", "Unknown")
        page_number = result.get("page_number") or 0
        title = result.get("title") or source_file
        content = result.get("content", "")
        blocks.append(
            f"[Document {index}] {title}\n"
            f"Source: {source_file}, Page {page_number}\n"
            f"Content: {content}"
        )
    return "\n\n".join(blocks)


def generate_response(
    user_message: str,
    conversation_history: List[Dict],
) -> Tuple[str, List[Citation]]:
    search_results = search_manuals(user_message)
    context = _build_context(search_results)

    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in conversation_history[-10:]:
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append(
        {
            "role": "user",
            "content": (
                f"Context from service manuals:\n{context}\n\n"
                f"Technician's question: {user_message}"
            ),
        }
    )

    completion = get_openai_client().chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=messages,
        temperature=0.2,
    )
    answer_text = (completion.choices[0].message.content or "").strip()
    if not answer_text:
        answer_text = "I couldn't find enough information in the manuals to answer that."

    citations = [
        Citation(
            source_file=result.get("source_file", "Unknown"),
            page_number=int(result.get("page_number") or 0),
            content_snippet=result.get("content", "")[:400],
        )
        for result in search_results
    ]

    return answer_text, citations
