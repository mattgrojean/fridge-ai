from pathlib import Path
from typing import Dict, List
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from auth import auth_middleware, get_current_user
from chat import generate_response
from config import ENTRA_CLIENT_ID, ENTRA_TENANT_ID
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

conversation_store: Dict[str, List[dict]] = {}


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
        "redirectUri": "/",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    try:
        conversation_id = payload.conversation_id or str(uuid.uuid4())
        history = conversation_store.setdefault(conversation_id, [])
        answer, citations = generate_response(payload.message, history)

        history.append(
            {
                "role": "user",
                "content": payload.message,
                "user": user.get("email") or user.get("name"),
            }
        )
        history.append({"role": "assistant", "content": answer})
        conversation_store[conversation_id] = history[-20:]

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error"},
    )
