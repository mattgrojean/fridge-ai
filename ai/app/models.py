from typing import List, Literal, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None


class OCRRequest(BaseModel):
    """Image upload for OCR extraction — the image is sent as multipart form data."""

    pass


class OCRResponse(BaseModel):
    text: str


class Citation(BaseModel):
    document_id: str
    blob_name: str
    display_title: str
    source_file: str
    page_number: int
    snippet: str
    content_snippet: str


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    conversation_id: str
    message_index: int = -1


# ---------------------------------------------------------------------------
# Conversation history models
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    citations: List[Citation] = []
    timestamp: str = ""


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationDetail(BaseModel):
    id: str
    user_oid: str
    created_at: str
    updated_at: str
    messages: List[Message]


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_index: int
    rating: Literal["up", "down"]
    comment: Optional[str] = None