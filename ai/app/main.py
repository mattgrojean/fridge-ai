from datetime import datetime, timezone
import logging
import os
import time
from pathlib import Path
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from auth import auth_middleware, get_current_user
from chat import generate_response
from config import ENTRA_API_SCOPE, ENTRA_CLIENT_ID, ENTRA_TENANT_ID
from conversation_store import ConversationStore
from manuals import resolve_document_link, get_citation_metadata, render_pdf_page
from models import (
    ChatRequest,
    ChatResponse,
    Citation,
    ConversationDetail,
    ConversationSummary,
    FeedbackRequest,
    Message,
)
import telemetry

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Appliance AI Chat")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(auth_middleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

store = ConversationStore()


def _user_oid(user: dict) -> str:
    return user.get("oid", "unknown")


def _user_name(user: dict) -> str:
    return user.get("name", user.get("email", "unknown"))


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


@app.get("/auth-config")
async def auth_config() -> dict:
    return {
        "clientId": ENTRA_CLIENT_ID,
        "tenantId": ENTRA_TENANT_ID,
        "apiScope": ENTRA_API_SCOPE,
        "redirectUri": "/",
    }


@app.get("/models")
async def list_models() -> list[dict]:
    """Return the available model deployments for the model selector."""
    from config import FOUNDRY_MODEL_DEPLOYMENTS

    deployments = [
        d.strip() for d in FOUNDRY_MODEL_DEPLOYMENTS.split(",") if d.strip()
    ]
    return [{"id": d, "name": d} for d in deployments]


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    try:
        t0 = time.time()
        conversation_id = payload.conversation_id or str(uuid.uuid4())
        oid = _user_oid(user)

        foundry_conv_id = store.get_foundry_id(oid, conversation_id)
        answer, citations, foundry_conv_id = generate_response(
            payload.message, foundry_conv_id, model=payload.model
        )

        msg_idx = store.append_exchange(
            user_oid=oid,
            user_name=_user_name(user),
            conversation_id=conversation_id,
            foundry_conversation_id=foundry_conv_id,
            user_message=payload.message,
            answer=answer,
            citations=[c.model_dump() for c in citations],
        )

        telemetry.track_chat_query(
            user_oid=oid,
            conversation_id=conversation_id,
            query_length=len(payload.message),
            response_length=len(answer),
            citation_count=len(citations),
            foundry_conv_id=foundry_conv_id,
            elapsed_ms=(time.time() - t0) * 1000,
        )

        return ChatResponse(
            answer=answer,
            citations=citations,
            conversation_id=conversation_id,
            message_index=msg_idx,
        )
    except HTTPException:
        raise
    except Exception as exc:
        telemetry.track_error(
            user_oid=_user_oid(user),
            error_type=type(exc).__name__,
            error_message=str(exc),
            context="chat_endpoint",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Chat request failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Conversation history endpoints (Tier 1.1)
# ---------------------------------------------------------------------------


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: dict = Depends(get_current_user),
) -> list[ConversationSummary]:
    return [
        ConversationSummary(**s)
        for s in store.list_conversations(_user_oid(user))
    ]


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
) -> ConversationDetail:
    doc = store.get_conversation(_user_oid(user), conversation_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetail(
        id=doc["id"],
        user_oid=doc["user_oid"],
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        messages=[
            Message(
                role=m["role"],
                content=m["content"],
                citations=[Citation(**c) for c in m.get("citations", [])]
                if m.get("role") == "assistant"
                else [],
                timestamp=m.get("timestamp", ""),
            )
            for m in doc.get("messages", [])
        ],
    )


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    oid = _user_oid(user)

    # Clean up the Foundry-side conversation before removing our blob
    doc = store.get_conversation(oid, conversation_id)
    if doc and doc.get("foundry_conversation_id"):
        from chat import delete_foundry_conversation
        delete_foundry_conversation(doc["foundry_conversation_id"])

    deleted = store.delete_conversation(oid, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Feedback endpoint (Tier 1.2)
# ---------------------------------------------------------------------------


@app.post("/feedback")
async def submit_feedback(
    payload: FeedbackRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    oid = _user_oid(user)

    # Persist feedback on the conversation blob
    store.append_feedback(
        user_oid=oid,
        conversation_id=payload.conversation_id,
        message_index=payload.message_index,
        rating=payload.rating,
        comment=payload.comment,
    )

    telemetry.track_feedback(
        user_oid=oid,
        conversation_id=payload.conversation_id,
        rating=payload.rating,
        comment=payload.comment,
    )

    return {"status": "recorded"}


# ---------------------------------------------------------------------------
# OCR / vision endpoint
# ---------------------------------------------------------------------------


@app.post("/ocr")
async def ocr_image(
    image: UploadFile,
    user: dict = Depends(get_current_user),
) -> dict:
    """Extract text from an uploaded image using the vision model.

    Accepts multipart form data with a single ``image`` file field.
    Returns ``{"text": "extracted model numbers..."}``.
    """
    from vision import extract_text_from_image

    contents = await image.read()
    text = extract_text_from_image(contents, mime_type=image.content_type or "image/jpeg")
    return {"text": text}


# ---------------------------------------------------------------------------
# PDF page thumbnail (Tier 2.2)
# ---------------------------------------------------------------------------


@app.get("/documents/thumbnail")
async def document_thumbnail(
    document_id: str = Query(..., min_length=1),
    width: int = Query(400, ge=100, le=1200),
    user: dict = Depends(get_current_user),
) -> Response:
    """Render a page from the PDF as a PNG thumbnail."""
    meta = get_citation_metadata(document_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Document not found")

    blob_name = meta["blob_name"]
    page_number = meta["page_number"]
    if page_number is None:
        raise HTTPException(status_code=404, detail="Page number not available")

    # PyMuPDF uses 0-indexed pages
    png_bytes = render_pdf_page(blob_name, page_number - 1, max_width=width)
    if png_bytes is None:
        raise HTTPException(status_code=404, detail="Unable to render page")

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# Document resolution (existing)
# ---------------------------------------------------------------------------


@app.get("/documents/resolve")
async def resolve_document(
    document_id: str = Query(..., min_length=1),
    user: dict = Depends(get_current_user),
) -> dict:
    resolved_document = resolve_document_link(document_id)
    if resolved_document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return resolved_document


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error"},
    )
