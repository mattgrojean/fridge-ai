"""
Lightweight custom-event telemetry via Application Insights ingestion endpoint.

Avoids OpenTelemetry SDK weight — posts JSON directly to the ingestion API.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _ingestion_url() -> str | None:
    """Extract the IngestionEndpoint from the App Insights connection string."""
    conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not conn_str:
        return None
    parts = dict(p.split("=", 1) for p in conn_str.split(";") if "=" in p)
    endpoint = parts.get("IngestionEndpoint", "")
    if not endpoint:
        return None
    return f"{endpoint.rstrip('/')}/v2.1/track"


def _send_event(name: str, properties: dict[str, Any] | None = None) -> None:
    url = _ingestion_url()
    if not url:
        return

    body = [
        {
            "name": "Microsoft.ApplicationInsights.Event",
            "time": datetime.now(timezone.utc).isoformat(),
            "iKey": "",
            "data": {
                "baseType": "EventData",
                "baseData": {
                    "name": name,
                    "properties": properties or {},
                },
            },
        }
    ]

    try:
        httpx.post(url, json=body, timeout=httpx.Timeout(5.0))
    except Exception:
        logger.debug("Failed to send telemetry event %s", name, exc_info=True)


# -- Public helpers used by the application --------------------------------


def track_chat_query(
    user_oid: str,
    conversation_id: str,
    query_length: int,
    response_length: int,
    citation_count: int,
    foundry_conv_id: str,
    elapsed_ms: float,
    error: str | None = None,
) -> None:
    _send_event(
        "ChatQuery",
        {
            "user_oid": user_oid,
            "conversation_id": conversation_id,
            "query_length": str(query_length),
            "response_length": str(response_length),
            "citation_count": str(citation_count),
            "foundry_conv_id": foundry_conv_id or "",
            "elapsed_ms": str(int(elapsed_ms)),
            "error": error or "",
        },
    )


def track_feedback(
    user_oid: str,
    conversation_id: str,
    rating: str,
    comment: str | None = None,
) -> None:
    _send_event(
        "ChatFeedback",
        {
            "user_oid": user_oid,
            "conversation_id": conversation_id,
            "rating": rating,
            "comment": comment or "",
        },
    )


def track_error(
    user_oid: str,
    error_type: str,
    error_message: str,
    context: str = "",
) -> None:
    _send_event(
        "AppError",
        {
            "user_oid": user_oid,
            "error_type": error_type,
            "error_message": error_message[:500],
            "context": context[:500],
        },
    )
