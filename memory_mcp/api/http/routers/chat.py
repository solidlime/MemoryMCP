from __future__ import annotations

import json
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse, StreamingResponse

from memory_mcp.api.http.deps import _resolve_persona_from_request, _safe_get_context
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)


def register_chat_routes(mcp) -> None:

    @mcp.custom_route("/api/chat/{persona}/config", methods=["GET"])
    async def get_chat_config(request: Request) -> JSONResponse:
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        from memory_mcp.domain.chat_config import ChatConfigRepository

        repo = ChatConfigRepository(ctx.connection.get_memory_db())
        config = repo.get(persona)
        return JSONResponse(config.to_safe_dict())

    @mcp.custom_route("/api/chat/{persona}/config", methods=["POST"])
    async def save_chat_config(request: Request) -> JSONResponse:
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        from memory_mcp.domain.chat_config import ChatConfig, ChatConfigRepository

        repo = ChatConfigRepository(ctx.connection.get_memory_db())
        current = repo.get(persona)

        update_data = current.model_dump()
        for field_name in (
            "provider",
            "model",
            "base_url",
            "system_prompt",
            "temperature",
            "max_tokens",
            "max_window_turns",
            "max_tool_calls",
            "auto_extract",
            "extract_model",
            "extract_max_tokens",
            "tool_result_max_chars",
            "mcp_servers",
        ):
            if field_name in body:
                update_data[field_name] = body[field_name]
        if "api_key" in body and body["api_key"] and not str(body["api_key"]).endswith("****"):
            update_data["api_key"] = body["api_key"]

        try:
            new_config = ChatConfig(**update_data)
        except Exception as e:
            return JSONResponse({"error": f"Invalid config: {e}"}, status_code=400)

        repo.save(new_config)
        return JSONResponse(new_config.to_safe_dict())

    @mcp.custom_route("/api/chat/{persona}", methods=["POST"])
    async def chat_endpoint(request: Request) -> StreamingResponse:
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:

            async def not_found():
                yield f"data: {json.dumps({'type': 'error', 'message': 'Persona not found'})}\n\n"

            return StreamingResponse(not_found(), media_type="text/event-stream")

        try:
            body = await request.json()
        except Exception:

            async def bad_request():
                yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid JSON'})}\n\n"

            return StreamingResponse(bad_request(), media_type="text/event-stream")

        user_message = (body.get("message") or "").strip()
        session_id = (body.get("session_id") or "default").strip()

        if not user_message:

            async def empty():
                yield f"data: {json.dumps({'type': 'error', 'message': 'message is required'})}\n\n"

            return StreamingResponse(empty(), media_type="text/event-stream")

        from memory_mcp.application.chat_service import ChatService
        from memory_mcp.domain.chat_config import ChatConfigRepository

        repo = ChatConfigRepository(ctx.connection.get_memory_db())
        config = repo.get(persona)
        service = ChatService()

        async def generate():
            async for chunk in service.chat(ctx, config, session_id, user_message):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
