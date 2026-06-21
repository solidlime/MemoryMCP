"""PromptBuildStep: systemプロンプトの組み立て。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)


class PromptBuildStep:
    """systemプロンプトを組み立てる。"""

    def __init__(self) -> None:
        pass

    def run(
        self,
        ctx: AppContext,
        config: ChatConfig,
        turn_ctx: ChatTurnContext,
    ) -> None:
        """ChatTurnContext.system_prompt を設定する。同期メソッド。"""
        persona = ctx.persona

        base_system = config.system_prompt or f"あなたは{persona}という名前のアシスタントです。"
        parts = [base_system]

        if turn_ctx.context_section:
            parts.append(f"\n--- ペルソナ状態・コンテキスト ---\n{turn_ctx.context_section}")
        if turn_ctx.related_memories:
            parts.append(f"\n--- 関連記憶 ---\n{turn_ctx.related_memories}")

        skills_raw: list[dict] = []
        if config.enabled_skills:
            try:
                from memory_mcp.config.settings import get_settings
                from memory_mcp.domain.skill import SkillRepository
                from memory_mcp.infrastructure.sqlite.connection import get_global_skills_db

                skill_repo = SkillRepository(get_global_skills_db(get_settings().data_root))
                skills = [skill_repo.get(n) for n in config.enabled_skills]
                skill_lines = []
                for s in skills:
                    if not s:
                        continue
                    line = f"- {s.name}: {s.description}"
                    if s.content and len(s.content) < 500:
                        content_preview = s.content.strip().split("\n")[0][:200]
                        line += f"\n  {content_preview}"
                    skill_lines.append(line)
                skills_raw = [s.model_dump() for s in skills if s]
                if skill_lines:
                    parts.append("\n--- 利用可能なSkill ---\n" + "\n".join(skill_lines))
            except Exception as e:
                logger.warning("PromptBuildStep: skills load failed: %s", e)

        turn_ctx.system_prompt = "\n".join(parts)
        turn_ctx.skills_raw = skills_raw
