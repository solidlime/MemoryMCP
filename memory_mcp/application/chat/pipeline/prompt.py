"""PromptBuildStep: systemプロンプトの組み立て。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)


class PromptBuildStep:
    """systemプロンプトを組み立てる。"""

    def run(
        self,
        ctx: AppContext,
        config: ChatConfig,
        turn_ctx: ChatTurnContext,
    ) -> None:
        """ChatTurnContext.system_prompt を設定する。同期メソッド。"""
        persona = ctx.persona
        now = get_now()
        jst_now = now.strftime("%Y-%m-%d %H:%M JST")

        base_system = config.system_prompt or f"あなたは{persona}という名前のアシスタントです。"
        parts = [base_system, f"\n現在時刻: {jst_now}"]

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
                skill_lines = [f"- {s.name}: {s.description}" for s in skills if s]
                skills_raw = [s.model_dump() for s in skills if s]
                if skill_lines:
                    parts.append("\n--- 利用可能なSkill ---\n" + "\n".join(skill_lines))
            except Exception as e:
                logger.warning("PromptBuildStep: skills load failed: %s", e)

        if config.enable_memory_tools:
            parts.append(
                "\n--- 記憶ツール使用ガイド ---\n"
                "目標や約束に関するツール:\n"
                "- goal_create: ユーザーが目標・計画を表明したら使う\n"
                "- goal_achieve / goal_cancel: 目標の完了・中止を記録\n"
                "- promise_create: 約束・コミットメントを記録\n"
                "- promise_fulfill: 約束の履行を記録\n"
                "- context_recall: tags=['goal','active'] で現在の目標一覧を確認"
            )

        turn_ctx.system_prompt = "\n".join(parts)
        turn_ctx.skills_raw = skills_raw
