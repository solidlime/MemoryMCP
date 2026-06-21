"""Auto-generated from tools.py split — _tools_sandbox.py."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext


async def _tool_sandbox(ctx: AppContext, persona: str, code: str, language: str = "python") -> str:
    from memory_mcp.config.settings import get_settings

    settings = get_settings()
    if not settings.sandbox.enabled:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox",
                "params_summary": f"language={language}, code={code[:50]}...",
                "result_summary": "Sandbox is not enabled",
                "success": False,
            },
        )
        return "Sandbox is not enabled."
    from memory_mcp.application.sandbox.service import get_sandbox_session

    session = get_sandbox_session(persona)
    try:
        result = await session.execute(code, language=language)
        parts = []
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append(f"[stderr] {result.stderr}")
        if result.exit_code != 0:
            parts.append(f"[exit code: {result.exit_code}]")
        if result.artifacts:
            parts.append(f"[artifacts: {len(result.artifacts)} image(s) generated]")
            for i, b64 in enumerate(result.artifacts):
                parts.append(f"[artifact_{i}: data:image/png;base64,{b64}]")
        result_text = "\n".join(parts) if parts else "(no output)"
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox",
                "params_summary": f"language={language}, code={code[:50]}...",
                "result_summary": f"Output ({len(result_text)} chars), exit_code={result.exit_code}",
                "success": True,
            },
        )
        return result_text
    except Exception as e:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox",
                "params_summary": f"language={language}, code={code[:50]}...",
                "result_summary": f"Sandbox error: {e}",
                "success": False,
            },
        )
        return f"Sandbox error: {e}"


async def _tool_sandbox_files(
    ctx: AppContext,
    persona: str,
    operation: str,
    path: str = "/sandbox",
    content: str | None = None,
) -> dict:
    from memory_mcp.config.settings import get_settings

    settings = get_settings()
    if not settings.sandbox.enabled:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox_files",
                "params_summary": f"operation={operation}, path={path}",
                "result_summary": "Sandbox is not enabled",
                "success": False,
            },
        )
        return {"ok": False, "error": "Sandbox is not enabled."}
    from memory_mcp.application.sandbox.service import get_sandbox_session

    if not path.startswith("/sandbox"):
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox_files",
                "params_summary": f"operation={operation}, path={path}",
                "result_summary": "path must be under /sandbox",
                "success": False,
            },
        )
        return {"ok": False, "error": "path must be under /sandbox"}
    sandbox_session = get_sandbox_session(persona)
    import base64 as _b64

    if operation == "list":
        files = await sandbox_session.list_files(path)
        file_list = [{"name": f.name, "path": f.path, "is_dir": f.is_dir, "size": f.size} for f in files]
        result = {"ok": True, "files": file_list}
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox_files",
                "params_summary": f"operation=list, path={path}",
                "result_summary": f"Listed {len(file_list)} files",
                "success": True,
            },
        )
        return result
    elif operation == "read":
        try:
            img_data = await sandbox_session.read_image(path)
            resp: dict = {
                "ok": True,
                "content_type": img_data["content_type"],
                "content_base64": img_data["content_base64"],
                "size": img_data["size"],
            }
            if img_data.get("resized"):
                resp["resized"] = True
                resp["orig_dims"] = img_data.get("orig_dims", "")
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "sandbox_files",
                    "params_summary": f"operation=read, path={path}",
                    "result_summary": f"Read image ({img_data['size']} bytes)",
                    "success": True,
                },
            )
            return resp
        except Exception:
            raw = await sandbox_session.read_file(path)
            is_image = False
            content_type = None
            if len(raw) >= 4:
                if raw[:4] == b"\x89PNG":
                    is_image, content_type = True, "image/png"
                elif raw[:2] == b"\xff\xd8":
                    is_image, content_type = True, "image/jpeg"
                elif raw[:3] == b"GIF":
                    is_image, content_type = True, "image/gif"
                elif len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
                    is_image, content_type = True, "image/webp"
            if is_image:
                b64_str = _b64.b64encode(raw).decode("ascii")
                result = {"ok": True, "content_type": content_type, "content_base64": b64_str, "size": len(raw)}
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "sandbox_files",
                        "params_summary": f"operation=read, path={path}",
                        "result_summary": f"Read image ({len(raw)} bytes)",
                        "success": True,
                    },
                )
                return result
            max_read = 8192
            truncated = len(raw) > max_read
            text = raw[:max_read].decode("utf-8", errors="replace")
            if truncated:
                result = {"ok": True, "content": text, "truncated": True, "total_bytes": len(raw)}
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "sandbox_files",
                        "params_summary": f"operation=read, path={path}",
                        "result_summary": f"Read file ({len(raw)} bytes, truncated)",
                        "success": True,
                    },
                )
                return result
            result = {"ok": True, "content": text}
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "sandbox_files",
                    "params_summary": f"operation=read, path={path}",
                    "result_summary": f"Read file ({len(raw)} bytes)",
                    "success": True,
                },
            )
            return result
    elif operation == "write":
        if not content:
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "sandbox_files",
                    "params_summary": f"operation=write, path={path}",
                    "result_summary": "content is required for write",
                    "success": False,
                },
            )
            return {"ok": False, "error": "content is required for write"}
        b64 = _b64.b64encode(content.encode()).decode()
        write_code = (
            f"import base64, os\n"
            f"_d = base64.b64decode({b64!r})\n"
            f"os.makedirs(os.path.dirname({path!r}) or '.', exist_ok=True)\n"
            f"open({path!r}, 'wb').write(_d)\n"
            f"print('written', len(_d), 'bytes')"
        )
        exec_result = await sandbox_session.execute(write_code)
        result = {"ok": True, "path": path, "stdout": exec_result.stdout.strip()}
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox_files",
                "params_summary": f"operation=write, path={path}",
                "result_summary": f"Wrote {len(content)} bytes to {path}",
                "success": True,
            },
        )
        return result
    elif operation == "delete":
        deleted = await sandbox_session.delete_file(path)
        if deleted:
            result = {"ok": True, "path": path}
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "sandbox_files",
                    "params_summary": f"operation=delete, path={path}",
                    "result_summary": f"Deleted {path}",
                    "success": True,
                },
            )
            return result
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox_files",
                "params_summary": f"operation=delete, path={path}",
                "result_summary": f"Delete failed for {path}",
                "success": False,
            },
        )
        return {"ok": False, "error": "delete failed", "path": path}
    else:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "sandbox_files",
                "params_summary": f"operation={operation}, path={path}",
                "result_summary": f"Unknown operation: {operation}",
                "success": False,
            },
        )
        return {"ok": False, "error": f"Unknown operation: {operation}. Use list/read/write/delete."}


# --- Goal/Promise tools ---
