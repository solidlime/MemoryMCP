from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from starlette.responses import StreamingResponse

from memory_mcp.api.http.deps import _resolve_persona_from_request, _safe_get_context
from memory_mcp.application.event_bus import (
    EVENT_CONTEXT_UPDATED,
    EVENT_MEMORY_CREATED,
    EVENT_MEMORY_DELETED,
    EVENT_MEMORY_UPDATED,
)
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)

_ALL_EVENT_TYPES = frozenset({
    EVENT_MEMORY_CREATED,
    EVENT_MEMORY_UPDATED,
    EVENT_MEMORY_DELETED,
    EVENT_CONTEXT_UPDATED,
})


def register_events_routes(mcp) -> None:
    """Register SSE events endpoint."""

    @mcp.custom_route("/api/events/{persona}", methods=["GET"])
    async def events_sse(request: Request) -> StreamingResponse:
        """SSE streaming endpoint for real-time event delivery.

        Query params:
            topics: comma-separated event type prefixes (e.g. "memory,context")
                    If omitted, all event types are delivered.
        """
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            async def not_found():
                yield f"event: error\ndata: {json.dumps({'message': 'Persona not found'})}\n\n"
            return StreamingResponse(not_found(), media_type="text/event-stream")

        # Parse topic filter
        topics_param = request.query_params.get("topics", "")
        topic_prefixes = [t.strip() for t in topics_param.split(",") if t.strip()] if topics_param else []

        # Determine which event types to subscribe to
        if topic_prefixes:
            subscribed_events = {
                et for et in _ALL_EVENT_TYPES
                if any(et.startswith(tp) or et == tp for tp in topic_prefixes)
            }
        else:
            subscribed_events = set(_ALL_EVENT_TYPES)

        queue: asyncio.Queue = asyncio.Queue()

        # Create subscriber handler
        async def on_event(event_type: str, data: dict):
            if event_type in subscribed_events:
                await queue.put((event_type, data))

        # Subscribe to EventBus
        for et in subscribed_events:
            ctx.event_bus.subscribe(et, on_event)

        async def event_stream():
            try:
                # Initial connection confirmation
                yield "event: connected\ndata: {}\n\n"

                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event_type, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                        payload = json.dumps(data, ensure_ascii=False, default=str)
                        yield f"event: {event_type}\ndata: {payload}\n\n"
                    except TimeoutError:
                        # Keepalive comment (SSE spec: lines starting with : are comments)
                        yield ": keepalive\n\n"
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug("SSE stream error for persona '%s': %s", persona, e)
            finally:
                # Unsubscribe on disconnect
                for et in subscribed_events:
                    ctx.event_bus.unsubscribe(et, on_event)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
