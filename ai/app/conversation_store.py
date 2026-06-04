"""
Azure Blob Storage-backed conversation persistence.

Replaces the in-memory dict in main.py so conversations survive
container restarts and scale-to-zero events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

from config import AZURE_CLIENT_ID, AZURE_STORAGE_ACCOUNT_NAME
from manuals import get_blob_service_client  # reuse the cached helper

logger = logging.getLogger(__name__)

CONVERSATIONS_CONTAINER = "conversations"


def _blob_path(user_oid: str, conversation_id: str) -> str:
    return f"{user_oid}/{conversation_id}.json"


def _create_blob_client() -> BlobServiceClient | None:
    """Create the blob client, returning None if Azure is unavailable (dev).

    The conversations container is provisioned by Terraform — we never
    try to create it here to avoid blocking on credential resolution
    when running outside Azure.
    """
    try:
        return get_blob_service_client()
    except Exception:
        logger.warning("Blob storage unavailable — conversations not persisted", exc_info=True)
        return None


class ConversationStore:
    """Persist conversation metadata and messages as JSON blobs.

    Authentication is deferred until the first read/write call, so the
    module can be imported without an Azure connection (dev/testing).
    """

    def __init__(self) -> None:
        self._client = None

    @property
    def _blob_client(self) -> BlobServiceClient | None:
        if self._client is None:
            self._client = _create_blob_client()
        return self._client

    @property
    def _ready(self) -> bool:
        """True when the blob client is available for reads/writes."""
        return self._blob_client is not None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get_foundry_id(self, user_oid: str, conversation_id: str) -> str | None:
        """Return the Foundry conversation ID for an app conversation, if known."""
        if not self._ready:
            return None
        doc = self._load(user_oid, conversation_id)
        return doc.get("foundry_conversation_id") if doc else None

    def append_exchange(
        self,
        user_oid: str,
        user_name: str,
        conversation_id: str,
        foundry_conversation_id: str,
        user_message: str,
        answer: str,
        citations: list[dict] | None = None,
    ) -> int:
        """Record a user → assistant exchange, creating the conversation if new.

        Returns the index of the assistant message in the messages array,
        so the frontend can send feedback against it.
        """
        if not self._ready:
            return -1

        now = datetime.now(timezone.utc).isoformat()

        doc = self._load(user_oid, conversation_id) or {
            "id": conversation_id,
            "user_oid": user_oid,
            "user_name": user_name,
            "created_at": now,
            "foundry_conversation_id": foundry_conversation_id,
            "messages": [],
        }

        doc["foundry_conversation_id"] = foundry_conversation_id
        doc["updated_at"] = now

        doc["messages"].append({
            "role": "user",
            "content": user_message,
            "timestamp": now,
        })
        doc["messages"].append({
            "role": "assistant",
            "content": answer,
            "citations": citations or [],
            "timestamp": now,
        })

        self._save(user_oid, conversation_id, doc)
        return len(doc["messages"]) - 1  # index of the just-added assistant message

    def list_conversations(
        self, user_oid: str, limit: int = 50
    ) -> list[dict]:
        """Return metadata for the user's most recent conversations."""
        if not self._ready:
            return []
        container = self._blob_client.get_container_client(CONVERSATIONS_CONTAINER)
        blobs = container.list_blobs(name_starts_with=f"{user_oid}/")
        summaries: list[dict] = []

        for blob in sorted(
            blobs, key=lambda b: b.last_modified, reverse=True
        ):
            conversation_id = blob.name.removeprefix(f"{user_oid}/").removesuffix(".json")
            doc = self._load(user_oid, conversation_id)
            if not (doc and doc.get("messages")):
                continue

            first_user = next(
                (m["content"] for m in doc["messages"] if m.get("role") == "user"), ""
            )
            summaries.append({
                "id": doc["id"],
                "title": first_user[:120] if first_user else "(empty)",
                "created_at": doc.get("created_at", ""),
                "updated_at": doc.get("updated_at", ""),
                "message_count": len(doc["messages"]),
            })

            if len(summaries) >= limit:
                break

        return summaries

    def get_conversation(self, user_oid: str, conversation_id: str) -> dict | None:
        """Return the full conversation document including all messages."""
        if not self._ready:
            return None
        return self._load(user_oid, conversation_id)

    def append_feedback(
        self,
        user_oid: str,
        conversation_id: str,
        message_index: int,
        rating: str,
        comment: str | None = None,
    ) -> None:
        """Tag a specific assistant message with feedback."""
        if not self._ready:
            return
        doc = self._load(user_oid, conversation_id)
        if not doc:
            return

        messages = doc.get("messages", [])
        if 0 <= message_index < len(messages):
            messages[message_index]["feedback"] = rating
            if comment:
                messages[message_index]["feedback_comment"] = comment
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(user_oid, conversation_id, doc)

    def delete_conversation(self, user_oid: str, conversation_id: str) -> bool:
        """Delete a conversation blob. Returns True if it existed."""
        if not self._ready:
            return False
        container = self._blob_client.get_container_client(CONVERSATIONS_CONTAINER)
        try:
            container.delete_blob(_blob_path(user_oid, conversation_id))
            return True
        except ResourceNotFoundError:
            return False

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _load(self, user_oid: str, conversation_id: str) -> dict | None:
        container = self._blob_client.get_container_client(CONVERSATIONS_CONTAINER)
        try:
            blob = container.download_blob(_blob_path(user_oid, conversation_id))
            return json.loads(blob.readall().decode("utf-8"))
        except ResourceNotFoundError:
            return None

    def _save(self, user_oid: str, conversation_id: str, doc: dict) -> None:
        container = self._blob_client.get_container_client(CONVERSATIONS_CONTAINER)
        container.upload_blob(
            _blob_path(user_oid, conversation_id),
            json.dumps(doc, ensure_ascii=False, default=str),
            overwrite=True,
        )
