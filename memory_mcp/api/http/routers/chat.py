from __future__ import annotations

import json
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse, Response, StreamingResponse

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
            "enabled_skills",
            "reflection_enabled",
            "reflection_threshold",
            "reflection_min_interval_hours",
            "session_summarize",
            "retrieval_recency_weight",
            "retrieval_importance_weight",
            "retrieval_relevance_weight",
            "display_history_turns",
            "housekeeping_threshold",
            "sandbox_enabled",
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
        debug_mode = bool(body.get("debug", False))

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
            async for chunk in service.chat(ctx, config, session_id, user_message, debug=debug_mode):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @mcp.custom_route("/api/chat/{persona}/commitments", methods=["GET"])
    async def get_chat_commitments(request: Request) -> JSONResponse:
        """アクティブなgoals・promises・最新リフレクション洞察を返す。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)

        goals: list[dict] = []
        promises: list[dict] = []
        insights: list[str] = []

        try:
            goal_result = ctx.memory_service.get_by_tags(["goal", "active"])
            if goal_result.is_ok and goal_result.value:
                goals = [{"content": m.content, "key": m.key} for m in goal_result.value]
        except Exception as e:
            logger.warning("get_chat_commitments: goals failed: %s", e)

        try:
            promise_result = ctx.memory_service.get_by_tags(["promise", "active"])
            if promise_result.is_ok and promise_result.value:
                promises = [{"content": m.content, "key": m.key} for m in promise_result.value]
        except Exception as e:
            logger.warning("get_chat_commitments: promises failed: %s", e)

        try:
            reflection_result = ctx.memory_service.get_by_tags(["reflection"])
            if reflection_result.is_ok and reflection_result.value:
                sorted_refs = sorted(
                    reflection_result.value,
                    key=lambda m: getattr(m, "created_at", None) or "",
                    reverse=True,
                )
                insights = [m.content for m in sorted_refs[:5]]
        except Exception as e:
            logger.warning("get_chat_commitments: insights failed: %s", e)

        return JSONResponse({"goals": goals, "promises": promises, "insights": insights})

    @mcp.custom_route("/api/chat/{persona}/sessions/{session_id}", methods=["GET"])
    async def get_chat_session(request: Request) -> JSONResponse:
        """F2: 会話履歴復元 — セッションのメッセージ一覧を返す。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        session_id = request.path_params.get("session_id", "")
        if not session_id:
            return JSONResponse({"error": "session_id required"}, status_code=400)

        from memory_mcp.application.chat.session_store import SessionManager

        db = ctx.connection.get_memory_db()
        messages = SessionManager.get_messages(db, persona, session_id)
        return JSONResponse({"session_id": session_id, "messages": messages})

    @mcp.custom_route("/api/chat/{persona}/sessions/{session_id}", methods=["DELETE"])
    async def delete_chat_session(request: Request) -> JSONResponse:
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        session_id = request.path_params.get("session_id", "")
        if not session_id:
            return JSONResponse({"error": "session_id required"}, status_code=400)

        from memory_mcp.application.chat.service import _session_manager
        from memory_mcp.application.chat.session_store import SessionManager

        db = ctx.connection.get_memory_db()
        SessionManager.delete_session(db, persona, session_id)
        _session_manager.clear(persona, session_id)
        return JSONResponse({"deleted": True, "session_id": session_id})

    @mcp.custom_route("/api/chat/{persona}/housekeeping", methods=["POST"])
    async def run_housekeeping(request: Request) -> JSONResponse:
        """コンテキスト整理: staleなgoals/promises/itemsをLLMで判定・削除する。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)

        from memory_mcp.application.chat.memory_llm import run_context_housekeeping
        from memory_mcp.domain.chat_config import ChatConfigRepository

        repo = ChatConfigRepository(ctx.connection.get_memory_db())
        config = repo.get(persona)
        try:
            result = await run_context_housekeeping(ctx, config)
            return JSONResponse(result)
        except Exception as e:
            logger.warning("housekeeping failed: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    @mcp.custom_route("/api/chat/{persona}/sandbox/upload", methods=["POST"])
    async def sandbox_upload(request: Request) -> JSONResponse:
        """ファイルをサンドボックスにアップロードする。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        from memory_mcp.domain.chat_config import ChatConfigRepository

        chat_cfg = ChatConfigRepository(ctx.connection.get_memory_db()).get(persona)
        if not chat_cfg.sandbox_enabled:
            return JSONResponse({"error": "Sandbox not enabled for this persona"}, status_code=400)

        import os
        import tempfile

        from starlette.datastructures import UploadFile

        form = await request.form()
        upload: UploadFile = form.get("file")
        if not upload:
            return JSONResponse({"error": "file field required"}, status_code=400)

        suffix = os.path.splitext(upload.filename or "upload")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            tmp_path = tf.name
            tf.write(await upload.read())

        try:
            from memory_mcp.application.sandbox.service import get_sandbox_session

            session = get_sandbox_session(persona)
            filename = upload.filename or "upload"
            remote_path = await session.upload_file(tmp_path, filename)
            return JSONResponse({"filename": filename, "remote_path": remote_path})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        finally:
            with __import__("contextlib").suppress(Exception):
                os.unlink(tmp_path)

    @mcp.custom_route("/api/chat/{persona}/sandbox/files", methods=["GET"])
    async def sandbox_list_files(request: Request) -> JSONResponse:
        """サンドボックス内ファイル一覧を返す。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        from memory_mcp.domain.chat_config import ChatConfigRepository

        chat_cfg = ChatConfigRepository(ctx.connection.get_memory_db()).get(persona)
        if not chat_cfg.sandbox_enabled:
            return JSONResponse({"error": "Sandbox not enabled for this persona"}, status_code=400)

        path = request.query_params.get("path", "/workspace")
        from memory_mcp.application.sandbox.service import get_sandbox_session

        session = get_sandbox_session(persona)
        try:
            files = await session.list_files(path)
            return JSONResponse(
                {
                    "path": path,
                    "files": [{"name": f.name, "path": f.path, "is_dir": f.is_dir, "size": f.size} for f in files],
                }
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @mcp.custom_route("/api/chat/{persona}/sandbox/files/{filepath:path}", methods=["GET"])
    async def sandbox_download_file(request: Request) -> Response:
        """サンドボックスからファイルをダウンロードする。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        from memory_mcp.domain.chat_config import ChatConfigRepository

        chat_cfg = ChatConfigRepository(ctx.connection.get_memory_db()).get(persona)
        if not chat_cfg.sandbox_enabled:
            return JSONResponse({"error": "Sandbox not enabled for this persona"}, status_code=400)

        filepath = request.path_params.get("filepath", "")
        if not filepath.startswith("workspace/") and not filepath.startswith("/workspace/"):
            filepath = f"/workspace/{filepath}"
        elif not filepath.startswith("/"):
            filepath = f"/{filepath}"

        from memory_mcp.application.sandbox.service import get_sandbox_session

        session = get_sandbox_session(persona)
        try:
            data = await session.read_file(filepath)
            import os

            filename = os.path.basename(filepath)
            return Response(
                content=data,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @mcp.custom_route("/api/chat/{persona}/sandbox/execute", methods=["POST"])
    async def sandbox_execute(request: Request) -> JSONResponse:
        """サンドボックスでコードを実行する。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        from memory_mcp.domain.chat_config import ChatConfigRepository

        chat_cfg = ChatConfigRepository(ctx.connection.get_memory_db()).get(persona)
        if not chat_cfg.sandbox_enabled:
            return JSONResponse({"error": "Sandbox not enabled for this persona"}, status_code=400)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        code = body.get("code", "")
        language = body.get("language", "python")
        if not code:
            return JSONResponse({"error": "code field required"}, status_code=400)

        from memory_mcp.application.sandbox.service import get_sandbox_session

        session = get_sandbox_session(persona)
        result = await session.execute(code, language=language)
        return JSONResponse(
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
            }
        )

    @mcp.custom_route("/api/chat/{persona}/sandbox/files/{filepath:path}", methods=["DELETE"])
    async def sandbox_delete_file(request: Request) -> JSONResponse:
        """サンドボックスのファイルを削除する。"""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        from memory_mcp.domain.chat_config import ChatConfigRepository

        chat_cfg = ChatConfigRepository(ctx.connection.get_memory_db()).get(persona)
        if not chat_cfg.sandbox_enabled:
            return JSONResponse({"error": "Sandbox not enabled for this persona"}, status_code=400)

        filepath = request.path_params.get("filepath", "")
        if not filepath.startswith("/"):
            filepath = f"/workspace/{filepath}"

        from memory_mcp.application.sandbox.service import get_sandbox_session

        session = get_sandbox_session(persona)
        ok = await session.delete_file(filepath)
        return JSONResponse({"deleted": ok, "path": filepath})
