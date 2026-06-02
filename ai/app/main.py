from pathlib import Path
from typing import Dict, Optional
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from auth import auth_middleware, get_current_user
from chat import generate_response
from config import ENTRA_API_SCOPE, ENTRA_CLIENT_ID, ENTRA_TENANT_ID
from manuals import resolve_document_link
from models import ChatRequest, ChatResponse

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

# Maps app-visible conversation UUID → Foundry conversation ID
conversation_store: Dict[str, Optional[str]] = {}


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


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    try:
        conversation_id = payload.conversation_id or str(uuid.uuid4())
        foundry_conv_id = conversation_store.get(conversation_id)
        answer, citations, foundry_conv_id = generate_response(payload.message, foundry_conv_id)
        conversation_store[conversation_id] = foundry_conv_id

        return ChatResponse(
            answer=answer,
            citations=citations,
            conversation_id=conversation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Chat request failed: {exc}",
        ) from exc


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
