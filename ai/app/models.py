from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


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