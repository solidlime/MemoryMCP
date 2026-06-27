"""Auto-generated from tools.py split — _tools_skill.py."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from nous.application.use_cases import AppContext


async def _tool_invoke_skill(ctx: AppContext, persona: str, name: str, task: str) -> dict:
    from nous.config.settings import get_settings
    from nous.domain.skill import SkillRepository
    from nous.infrastructure.llm.base import DoneEvent, LLMMessage, TextDeltaEvent
    from nous.infrastructure.llm.factory import get_provider
    from nous.infrastructure.sqlite.connection import get_global_skills_db

    skill_repo = SkillRepository(get_global_skills_db(get_settings().data_root))
    skill = skill_repo.get(name)
    if not skill:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "invoke_skill",
                "params_summary": f"name={name}, task={task[:50]}",
                "result_summary": f"Skill '{name}' not found",
                "success": False,
            },
        )
        return {"ok": False, "error": f"Skill '{name}' not found"}

    import json as _json

    from nous.domain.chat_config import ChatConfig

    chat_config_result = ctx.memory_repo.get_block("chat_config")
    config = None
    if chat_config_result.is_ok and chat_config_result.value:
        config = ChatConfig(**_json.loads(chat_config_result.value.get("content", "{}")))
    api_key = config.get_effective_api_key() if config else None
    if not api_key:
        from nous.config.runtime_config import RuntimeConfigManager

        _rcm = RuntimeConfigManager()
        api_key = (
            _rcm.get_effective_value("api_keys", "openrouter_api_key")[0]
            or _rcm.get_effective_value("api_keys", "anthropic_api_key")[0]
        )
        if not api_key:
            import os

            api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "invoke_skill",
                "params_summary": f"name={name}, task={task[:50]}",
                "result_summary": "No LLM API key configured",
                "success": False,
            },
        )
        return {"ok": False, "error": "No LLM API key configured"}
    provider_name = config.provider if config else "openrouter"
    model = config.get_effective_model() if config else "openai/gpt-4o-mini"
    base_url = config.get_effective_base_url() if config else None
    temperature = config.temperature if config else 0.7
    max_tokens = config.max_tokens if config else 2048
    try:
        provider = get_provider(provider_name, api_key, model, base_url)
    except Exception as e:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "invoke_skill",
                "params_summary": f"name={name}, task={task[:50]}",
                "result_summary": f"Provider init failed: {e}",
                "success": False,
            },
        )
        return {"ok": False, "error": f"Provider init failed: {e}"}
    text = ""
    try:
        async for event in provider.stream(
            messages=[LLMMessage(role="user", content=task)],
            system=skill.content,
            tools=[],
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if isinstance(event, TextDeltaEvent):
                text += event.content
            elif isinstance(event, DoneEvent):
                break
    except Exception as e:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "invoke_skill",
                "params_summary": f"name={name}, task={task[:50]}",
                "result_summary": f"Skill execution failed: {e}",
                "success": False,
            },
        )
        return {"ok": False, "error": f"Skill execution failed: {e}"}
    result = {"ok": True, "result": text or "(no response)"}
    await ctx.event_bus.publish(
        "tool.called",
        {
            "persona": persona,
            "tool_name": "invoke_skill",
            "params_summary": f"name={name}, task={task[:50]}",
            "result_summary": f"Skill '{name}' executed ({len(text)} chars)",
            "success": True,
        },
    )
    return result
