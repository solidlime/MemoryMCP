from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

from memory_mcp.api.http.deps import (
    _memory_to_dict,
    _resolve_persona_from_request,
    _safe_get_context,
)
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)


def register_search_routes(mcp) -> None:
    @mcp.custom_route("/api/search/{persona}", methods=["GET"])
    async def search_memories(request: Request) -> JSONResponse:
        persona = _resolve_persona_from_request(request)
        q = request.query_params.get("q", "")
        try:
            limit = int(request.query_params.get("limit", "20"))
            if limit < 1 or limit > 1000:
                return JSONResponse({"error": "limit must be between 1 and 1000"}, status_code=400)
        except ValueError:
            return JSONResponse({"error": "limit must be an integer"}, status_code=400)
        mode = request.query_params.get("mode", "hybrid")
        # mode parameter accepted for backwards compatibility; always uses hybrid internally
        if not q:
            return JSONResponse({"error": "Query parameter 'q' is required"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            from memory_mcp.domain.search.engine import SearchQuery

            query = SearchQuery(text=q, mode=mode, top_k=limit)
            if hasattr(ctx.search_engine, "_semantic") and ctx.search_engine._semantic is not None:
                ctx.search_engine._semantic._persona = persona  # noqa: SLF001

            result = ctx.search_engine.search(query)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse(
                {
                    "persona": persona,
                    "query": q,
                    "results": [
                        {
                            "memory": _memory_to_dict(r.memory),
                            "score": round(r.score, 4),
                            "source": r.source,
                        }
                        for r in result.value
                    ],
                }
            )
        except Exception as exc:
            logger.exception("Unexpected error: %s", exc)
            return JSONResponse({"error": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/emotions/{persona}", methods=["GET"])
    async def emotion_history(request: Request) -> JSONResponse:
        persona = _resolve_persona_from_request(request)
        try:
            days = int(request.query_params.get("days", "7"))
            if days < 1 or days > 365:
                return JSONResponse({"error": "days must be between 1 and 365"}, status_code=400)
        except ValueError:
            return JSONResponse({"error": "days must be an integer"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.persona_repo.get_emotion_history_by_days(persona, days)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            grouped: dict[str, list[dict]] = defaultdict(list)
            for record in result.value:
                date_str = record.timestamp.strftime("%Y-%m-%d") if record.timestamp else "unknown"
                grouped[date_str].append(
                    {
                        "emotion_type": record.emotion_type,
                        "intensity": record.intensity,
                        "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                        "trigger_memory_key": record.trigger_memory_key,
                        "context": record.context,
                    }
                )
            return JSONResponse(
                {
                    "persona": persona,
                    "days": days,
                    "history": dict(grouped),
                }
            )
        except Exception as exc:
            logger.exception("Unexpected error: %s", exc)
            return JSONResponse({"error": "Internal server error"}, status_code=500)

    @mcp.custom_route("/api/graph/{persona}", methods=["GET"])
    async def graph_data(request: Request) -> JSONResponse:
        persona = _resolve_persona_from_request(request)
        limit = int(request.query_params.get("limit", "200"))
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.memory_repo.find_recent(limit=limit)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            memories = result.value

            nodes = []
            edges = []
            edge_set = set()
            tag_to_keys: dict[str, list[str]] = defaultdict(list)

            for mem in memories:
                nodes.append(
                    {
                        "key": mem.key,
                        "content": mem.content[:100] if mem.content else "",
                        "tags": mem.tags or [],
                        "emotion_type": mem.emotion,
                        "importance": mem.importance,
                    }
                )
                for tag in mem.tags or []:
                    tag_to_keys[tag].append(mem.key)
                for related in mem.related_keys or []:
                    pair = tuple(sorted([mem.key, related]))
                    if pair not in edge_set:
                        edge_set.add(pair)
                        edges.append(
                            {
                                "source": mem.key,
                                "target": related,
                                "type": "related",
                            }
                        )

            for tag, keys in tag_to_keys.items():
                if len(keys) > 1:
                    capped = keys[:20]
                    for i in range(len(capped)):
                        for j in range(i + 1, len(capped)):
                            pair = tuple(sorted([capped[i], capped[j]]))
                            if pair not in edge_set:
                                edge_set.add(pair)
                                edges.append(
                                    {
                                        "source": capped[i],
                                        "target": capped[j],
                                        "type": "tag",
                                        "tag": tag,
                                    }
                                )

            return JSONResponse(
                {
                    "persona": persona,
                    "nodes": nodes,
                    "edges": edges,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                }
            )
        except Exception as exc:
            logger.exception("Unexpected error: %s", exc)
            return JSONResponse({"error": "Internal server error"}, status_code=500)
