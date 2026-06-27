"""Built-in tool executor and skill invocation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from memory_mcp.api.mcp.tools import TOOL_DISPATCH
from memory_mcp.application.chat.tools.definitions import _MEMORY_MCP_TOOL_NAMES
from memory_mcp.config.settings import get_settings
from memory_mcp.domain.skill import SkillRepository
from memory_mcp.infrastructure.logging.structured import get_logger
from memory_mcp.infrastructure.sqlite.connection import get_global_skills_db

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig
    from memory_mcp.infrastructure.llm.base import ToolDefinition

logger = get_logger(__name__)


def filter_extra_tools(extra_tools: list[ToolDefinition]) -> list[ToolDefinition]:
    """MCP extra ツールから memory 系重複ツールを除外する。"""
    return [t for t in extra_tools if t.name.split("__")[-1] not in _MEMORY_MCP_TOOL_NAMES]


def truncate_tool_result(result: dict, max_chars: int) -> dict:
    """Truncate tool result string to avoid context overflow."""
    has_images = "content_base64" in result or "artifacts" in result
    if has_images:
        logger.info(
            "truncate_tool_result: image data detected (content_base64=%s, artifacts=%d, content_type=%s)",
            "yes" if "content_base64" in result else "no",
            len(result.get("artifacts", [])),
            result.get("content_type", "unknown"),
        )
    if not has_images:
        result_str = json.dumps(result, ensure_ascii=False)
        if len(result_str) <= max_chars:
            return result
        remaining = len(result_str) - max_chars
        return {
            "truncated": True,
            "content": result_str[:max_chars] + f"... [truncated: {remaining} chars remaining]",
        }
    text_parts = {k: v for k, v in result.items() if k not in ("content_base64", "artifacts")}
    text_str = json.dumps(text_parts, ensure_ascii=False)
    if len(text_str) > max_chars:
        text_str = text_str[:max_chars] + "... [truncated]"
    output = {"content": text_str}
    if "content_base64" in result:
        output["content_base64"] = result["content_base64"]
        output["content_type"] = result.get("content_type", "image/png")
    if "artifacts" in result:
        output["artifacts"] = result["artifacts"]
    return output


# ── Builtin-only handlers (different from MCP counterparts) ──


async def _handle_context_update(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    update_kwargs: dict = {}
    if "emotion" in tool_input:
        update_kwargs["emotion"] = tool_input["emotion"]
    if "emotion_intensity" in tool_input:
        update_kwargs["emotion_intensity"] = float(tool_input["emotion_intensity"])
    if "mental_state" in tool_input:
        update_kwargs["mental_state"] = tool_input["mental_state"]
    if update_kwargs:
        if "emotion" in update_kwargs:
            ctx.persona_service.update_emotion(
                ctx.persona,
                update_kwargs["emotion"],
                update_kwargs.get("emotion_intensity", 0.5),
            )
        if "mental_state" in update_kwargs:
            ctx.persona_service.update_physical_state(
                ctx.persona,
                mental_state=update_kwargs["mental_state"],
            )
    # context_note: session continuity — persists in persona_info, displayed in get_context
    if "context_note" in tool_input and tool_input["context_note"]:
        ctx.persona_service.update_persona_info(ctx.persona, {"context_note": tool_input["context_note"]})
    return {"status": "ok"}


async def _handle_execute_code(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    if not getattr(config, "sandbox_enabled", False):
        return {"status": "error", "message": "sandbox が無効です。チャット設定で有効化してください。"}
    from memory_mcp.application.sandbox.service import get_sandbox_session

    code = tool_input.get("code", "")
    language = tool_input.get("language", "python")
    session_id = tool_input.get("session_id")

    if session_id:
        # Use persona-scoped session key to prevent cross-persona leaks
        sandbox_key = f"{ctx.persona}:{session_id}"
        sandbox = get_sandbox_session(sandbox_key)
    else:
        sandbox = get_sandbox_session(ctx.persona)

    result = await sandbox.execute(code, language)
    # Include session_id in response for LLM to reference next time
    response = {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "artifacts": result.artifacts,
    }
    if session_id:
        response["session_id"] = session_id
    return response


async def _handle_browser(
    ctx: AppContext, config: ChatConfig, tool_input: dict
) -> dict:  # pragma: no cover - external process
    """Execute agent-browser commands safely via subprocess."""
    import asyncio
    import json as _json

    action = (tool_input.get("action") or "").strip()
    if not action:
        return {"status": "error", "message": "action is required"}

    # ── Locate agent-browser binary ──
    agent_bin = _find_agent_browser(ctx.settings if hasattr(ctx, "settings") else None)
    if not agent_bin:
        return {
            "status": "error",
            "message": (
                "agent-browser not found. Install it:\n"
                "  npm install -g agent-browser\n"
                "  agent-browser install\n\n"
                "Or set MEMORY_MCP_AGENT_BROWSER_PATH=/path/to/agent-browser in .env"
            ),
        }

    # ── Build command args from action ──
    args: list[str] = [agent_bin]

    try:
        if action == "open":
            url = (tool_input.get("url") or "").strip()
            if not url:
                return {"status": "error", "message": "url is required for open"}
            if not url.startswith(("http://", "https://")):
                return {"status": "error", "message": "url must start with http:// or https://"}
            args.extend(["open", url])

        elif action == "snapshot":
            interactive = tool_input.get("interactive", True)
            args.append("snapshot")
            if interactive:
                args.append("-i")
            if tool_input.get("compact"):
                args.append("-c")
            selector = (tool_input.get("selector") or "").strip()
            if selector:
                args.extend(["-s", selector])
            args.append("--json")

        elif action == "click":
            ref = (tool_input.get("ref") or "").strip()
            if not ref:
                return {"status": "error", "message": "ref is required for click"}
            args.extend(["click", ref])

        elif action == "fill":
            ref = (tool_input.get("ref") or "").strip()
            value = tool_input.get("value", "")
            if not ref:
                return {"status": "error", "message": "ref is required for fill"}
            args.extend(["fill", ref, str(value)])

        elif action == "press":
            key = (tool_input.get("key") or "").strip()
            if not key:
                return {"status": "error", "message": "key is required for press"}
            args.extend(["press", key])

        elif action == "get":
            what = (tool_input.get("what") or "").strip()
            if not what:
                return {"status": "error", "message": "what is required for get"}
            if what == "count":
                selector = (tool_input.get("selector") or "").strip()
                if not selector:
                    return {"status": "error", "message": "selector is required for get count"}
                args.extend(["get", "count", selector])
            elif what in ("title", "url"):
                args.extend(["get", what])
            else:
                ref = (tool_input.get("ref") or "").strip()
                if not ref:
                    return {"status": "error", "message": f"ref is required for get {what}"}
                args.extend(["get", what, ref])

        elif action == "wait":
            until = (tool_input.get("until") or "").strip()
            value = (tool_input.get("value") or "").strip()
            if not until:
                return {"status": "error", "message": "until is required for wait"}
            if until == "text":
                if not value:
                    return {"status": "error", "message": "value is required for wait text"}
                args.extend(["wait", "--text", value])
            elif until == "url":
                if not value:
                    return {"status": "error", "message": "value is required for wait url"}
                args.extend(["wait", "--url", value])
            elif until == "load":
                args.extend(["wait", "--load", "networkidle"])
            else:
                return {"status": "error", "message": f"Unknown wait until: {until}"}

        elif action == "scroll":
            direction = (tool_input.get("direction") or "down").strip()
            amount = max(1, min(int(tool_input.get("amount", 300)), 5000))
            args.extend(["scroll", direction, str(amount)])

        elif action == "close":
            args.append("close")

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

        # ── Execute ──
        timeout = 30  # seconds
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        out_text = stdout.decode(errors="replace").strip()
        err_text = stderr.decode(errors="replace").strip()

        # Try parsing stdout as JSON (snapshot --json returns JSON)
        result: dict = {"status": "ok", "action": action}
        if action == "snapshot" and out_text:
            try:
                result["page"] = _json.loads(out_text)
            except _json.JSONDecodeError:
                result["text"] = out_text[:5000]
        elif action == "get":
            result["value"] = out_text[:5000]
        else:
            result["output"] = out_text[:5000]

        if proc.returncode != 0:
            result["status"] = "error"
            result["message"] = err_text[:500] or f"exit code {proc.returncode}"
            result["stderr"] = err_text[:500]

        return result

    except TimeoutError:
        return {"status": "error", "message": f"browser {action} timed out (30s limit)"}
    except Exception as e:
        return {"status": "error", "message": f"browser {action} failed: {str(e)[:200]}"}


async def _handle_search(
    ctx: AppContext, config: ChatConfig, tool_input: dict
) -> dict:  # pragma: no cover - external HTTP
    """Execute a web search via SearXNG meta-search engine."""
    import urllib.parse

    query = (tool_input.get("query") or "").strip()
    if not query:
        return {"status": "error", "message": "query is required"}

    num_results = int(tool_input.get("num_results", 10))
    lang = (tool_input.get("language") or "ja").strip()

    searxng_url = getattr(config, "searxng_url", "http://nas:11111")
    search_url = f"{searxng_url}/search?q={urllib.parse.quote(query)}&format=json&language={lang}"

    import httpx

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return {"status": "error", "message": "SearXNG search timed out (15s)"}
    except httpx.ConnectError:
        return {"status": "error", "message": f"SearXNG connection failed: {searxng_url}"}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "message": f"SearXNG returned HTTP {exc.response.status_code}"}
    except Exception as e:
        error_msg = str(e)[:200] if str(e) else type(e).__name__
        return {"status": "error", "message": f"SearXNG search failed: {error_msg}"}

    raw_results = data.get("results", [])
    limit = min(num_results, len(raw_results))
    results = []
    for r in raw_results[:limit]:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        content = (r.get("content") or "").strip()
        if title or content:
            results.append({"title": title, "url": url, "content": content})

    return {"status": "ok", "query": query, "results": results, "count": len(results)}


def _find_agent_browser(settings=None) -> str | None:
    """Find agent-browser binary. Checks Settings, env, data dir, PATH."""
    import os
    import shutil

    from memory_mcp.config.settings import get_settings

    s = settings or get_settings()

    # 1. Settings.agent_browser_path (env: MEMORY_MCP_AGENT_BROWSER_PATH)
    if s.agent_browser_path and os.path.isfile(s.agent_browser_path):
        return s.agent_browser_path

    # 2. Legacy AGENT_BROWSER_PATH (no prefix)
    path = os.environ.get("AGENT_BROWSER_PATH")
    if path and os.path.isfile(path):
        return path

    # 3. Data volume paths (Docker)
    data_root = os.environ.get("MEMORY_MCP_DATA_ROOT", "/opt/memory-mcp/data")
    candidates = [
        os.path.join(data_root, "agent-browser/bin/agent-browser"),
        os.path.expanduser("~/.local/nodejs/bin/agent-browser"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    # 4. PATH
    found = shutil.which("agent-browser") or shutil.which("agent-browser.cmd")
    if found:
        return found

    return None


# ── MCP-shared handlers (delegate to TOOL_DISPATCH) ──


async def _handle_mcp_dispatch(tool_name: str, ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    """Call shared MCP tool implementation via TOOL_DISPATCH."""
    if tool_name == "sandbox_files" and not getattr(config, "sandbox_enabled", False):
        return {"status": "error", "message": "sandbox が無効です。チャット設定で有効化してください。"}

    func = TOOL_DISPATCH.get(tool_name)
    if func is None:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    # ── Parameter mapping: builtin → MCP parameter name diff ──
    mapped_input = dict(tool_input)
    if tool_name == "memory_update" and "new_content" in mapped_input:
        mapped_input["content"] = mapped_input.pop("new_content")

    result_raw = await func(ctx, ctx.persona, **mapped_input)
    # Some MCP functions return JSON string, others return dict
    if isinstance(result_raw, str):
        try:
            result = json.loads(result_raw)
        except json.JSONDecodeError:
            return {"status": "ok", "content": result_raw}  # plain text response
    else:
        result = result_raw

    # Translate core dict format to builtin format
    if result.get("ok"):
        # memory_create duplicate case
        if result.get("status") == "duplicate":
            return {"status": "duplicate", "similar_to": result.get("similar_to", []), "message": result.get("message", "")}
        if "key" in result:
            return {"status": "ok", "key": result["key"]}
        if "memories" in result:
            return {"status": "ok", "memories": result["memories"]}
        if "status" in result:
            return {"status": "ok", "updated": result.get("content", "")}
        if "result" in result:
            return {"result": result["result"]}
        if "files" in result:
            return result  # sandbox_files list
        if "content_base64" in result:
            return result  # sandbox_files read (image)
        if "content" in result:
            return result  # sandbox_files read (text)
        if "path" in result:
            return {"status": "ok", "path": result.get("path", "")}
        return {"status": "ok"}
    return {"status": "error", "message": result.get("error", "unknown")}


# ── Image generation ──


async def _handle_image_generate(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    """DALL-E 3またはStable Diffusionで画像を生成する"""
    if not getattr(config, "image_gen_enabled", False):
        return {"status": "error", "message": "画像生成が無効です。チャット設定で有効化してください。"}

    prompt = str(tool_input.get("prompt", "")).strip()
    if not prompt:
        return {"status": "error", "message": "プロンプトが指定されていません"}

    size = str(tool_input.get("size", "1024x1024"))
    quality = str(tool_input.get("quality", "standard"))
    n = max(1, min(4, int(tool_input.get("n", 1))))
    provider_arg = str(tool_input.get("provider", "auto"))

    provider_name = getattr(config, "image_gen_provider", "openai") if provider_arg == "auto" else provider_arg

    try:
        # 開始イベントを送信
        if hasattr(ctx, "event_bus") and ctx.event_bus is not None:
            await ctx.event_bus.publish(
                "sse_event",
                {"type": "image_gen_start", "provider": provider_name, "prompt": prompt[:100], "n": n},
            )

        # プロバイダ選択
        if provider_name == "openai":
            from memory_mcp.infrastructure.image_gen.dalle import DalleProvider

            model = getattr(config, "image_gen_dalle_model", "dall-e-3")
            provider = DalleProvider(model=model)
        elif provider_name == "stability":
            from memory_mcp.infrastructure.image_gen.stability import StabilityProvider

            stability_url = getattr(config, "image_gen_stability_url", "")
            if not stability_url:
                return {"status": "error", "message": "Stable DiffusionのURLが設定されていません"}
            provider = StabilityProvider(api_url=stability_url)
        else:
            return {"status": "error", "message": f"未対応のプロバイダです: {provider_name}"}

        generated = await provider.generate(prompt=prompt, size=size, quality=quality, n=n)

        # 結果を構築
        images_data = [
            {
                "base64": img.base64,
                "revised_prompt": img.revised_prompt,
                "size": img.size,
            }
            for img in generated
        ]

        # 結果イベントを送信
        if hasattr(ctx, "event_bus") and ctx.event_bus is not None:
            await ctx.event_bus.publish(
                "sse_event",
                {"type": "image_gen_result", "images": images_data, "provider": provider_name},
            )

        # サマリーを返す（base64が大きくなるため全文はimagesに入れる）
        summary = f"{len(generated)}枚の画像を生成しました"
        if generated and generated[0].revised_prompt != prompt:
            summary += f"\n改訂プロンプト: {generated[0].revised_prompt}"

        return {
            "status": "success",
            "message": summary,
            "images": images_data,
        }

    except Exception as e:
        return {"status": "error", "message": f"画像生成に失敗しました: {str(e)}"}


# ── PDF reading ──


async def _handle_read_pdf(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    """PDFファイルを解析してテキスト・テーブル・画像を抽出する"""
    path = str(tool_input.get("path", "")).strip()
    if not path:
        return {"status": "error", "message": "PDFのパスが指定されていません"}

    try:
        import base64
        from pathlib import Path

        import fitz  # PyMuPDF

        pdf_path = Path(path)
        if not pdf_path.exists():
            return {"status": "error", "message": f"ファイルが見つかりません: {path}"}
        if pdf_path.suffix.lower() != ".pdf":
            return {"status": "error", "message": "PDFファイルではありません"}

        # ファイルサイズチェック (50MB上限)
        if pdf_path.stat().st_size > 50 * 1024 * 1024:
            return {"status": "error", "message": "PDFファイルが大きすぎます (上限: 50MB)"}

        doc = fitz.open(str(pdf_path))
        num_pages = len(doc)

        # テキスト抽出 (上限100,000文字)
        all_text_parts = []
        total_chars = 0
        text_limit = 100000

        for page in doc:
            text = page.get_text()
            if total_chars + len(text) > text_limit:
                remaining = text_limit - total_chars
                if remaining > 0:
                    all_text_parts.append(text[:remaining])
                all_text_parts.append("\n\n[テキストが上限に達したため切り捨てられました]")
                break
            all_text_parts.append(text)
            total_chars += len(text)

        full_text = "\n".join(all_text_parts)

        # テーブル抽出 (pdfplumber)
        tables = []
        try:
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables()
                    for table in page_tables:
                        if table and len(table) > 0:
                            headers = [str(h) if h else "" for h in table[0]]
                            rows = [[str(c) if c else "" for c in row] for row in table[1:]] if len(table) > 1 else []
                            tables.append(
                                {
                                    "page": i + 1,
                                    "headers": headers,
                                    "rows": rows[:50],  # 最大50行まで
                                }
                            )
        except Exception:
            pass  # pdfplumberが使えなくてもテキスト抽出は成功させる

        # 埋め込み画像抽出 (最大5枚、1MB/枚上限)
        images = []
        for page_num in range(num_pages):
            if len(images) >= 5:
                break
            page = doc[page_num]
            image_list = page.get_images(full=True)
            for img_info in image_list:
                if len(images) >= 5:
                    break
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                if len(image_bytes) > 1_000_000:  # 1MB上限
                    continue
                images.append(
                    {
                        "page": page_num + 1,
                        "base64": base64.b64encode(image_bytes).decode("utf-8"),
                        "mime_type": f"image/{base_image['ext']}",
                    }
                )

        doc.close()

        return {
            "status": "success",
            "filename": pdf_path.name,
            "pages": num_pages,
            "text": full_text,
            "tables": tables,
            "images": images,
        }

    except ImportError as e:
        missing = str(e).split("'")[1] if "'" in str(e) else str(e)
        return {
            "status": "error",
            "message": f"PDFライブラリが不足しています: {missing}。pip install PyMuPDF pdfplumber を実行してください",
        }
    except Exception as e:
        return {"status": "error", "message": f"PDFの解析に失敗しました: {str(e)}"}


async def _handle_list_skills(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    """List all registered skills from the skill store."""
    try:
        db = get_global_skills_db(get_settings().data_root)
        if db is None:
            return {"status": "error", "message": "Skill store not available"}

        repo = SkillRepository(db)
        skills = repo.list_all()
        items = [{"name": s.name, "description": getattr(s, "description", "")} for s in skills]
        return {"status": "ok", "skills": items, "count": len(items)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Handler dispatch table (replaces if/elif chain) ──

_BUILTIN_DISPATCH: dict[str, Any] = {
    "sandbox": _handle_execute_code,
    "list_skills": _handle_list_skills,
    "browser": _handle_browser,
    "search": _handle_search,
    "image_generate": _handle_image_generate,
    "read_pdf": _handle_read_pdf,
}

_MCP_SHARED_TOOLS = frozenset(
    {
        "goal_manage",
        "invoke_skill",
        "sandbox_files",
        "update_context",
        "memory_create",
        "memory_search",
        "memory_update",
    }
)


async def execute_tool(ctx: AppContext, config: ChatConfig, tool_name: str, tool_input: dict) -> dict:
    """Execute built-in or shared MCP tool via dispatch table."""
    try:
        # Builtin-specific handler
        handler = _BUILTIN_DISPATCH.get(tool_name)
        if handler is not None:
            return await handler(ctx, config, tool_input)

        # Shared MCP tool (delegates to TOOL_DISPATCH)
        if tool_name in _MCP_SHARED_TOOLS:
            return await _handle_mcp_dispatch(tool_name, ctx, config, tool_input)

        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return {"status": "error", "message": str(e)}


# invoke_skill is now handled via TOOL_DISPATCH → _tool_invoke_skill in tools.py
