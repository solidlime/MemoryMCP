"""Routine and situational analysis helpers."""

import sqlite3
from typing import Dict, Any
from datetime import datetime


def check_routines(
    persona: str,
    current_hour: int,
    current_weekday: str,
    db_path: str,
    top_k: int = 5,
    detailed: bool = False
) -> str:
    """
    Check for routine patterns at current time.

    Args:
        persona: Persona name
        current_hour: Current hour (0-23)
        current_weekday: Current weekday name
        db_path: Path to database
        top_k: Number of results to return
        detailed: Whether to include detailed analysis

    Returns:
        Formatted string with routine patterns
    """
    from core.time_utils import calculate_time_diff

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Standard routine check (current time ±1 hour)
            cursor.execute("""
                SELECT
                    action_tag,
                    tags,
                    content,
                    COUNT(*) as frequency,
                    MAX(created_at) as last_occurrence,
                    AVG(importance) as avg_importance
                FROM memories
                WHERE created_at > datetime('now', '-30 days')
                AND CAST(strftime('%H', created_at) AS INTEGER) BETWEEN ? AND ?
                GROUP BY COALESCE(action_tag, tags, substr(content, 1, 20))
                HAVING frequency >= 3
                ORDER BY frequency DESC, avg_importance DESC
                LIMIT ?
            """, (current_hour - 1, current_hour + 1, top_k))

            patterns = cursor.fetchall()

            result = f"💫 いつものパターン (現在: {current_hour}時台, {current_weekday}):\n"
            result += "=" * 60 + "\n\n"

            if patterns:
                for i, (action, tags, sample_content, freq, last_time, avg_imp) in enumerate(patterns, 1):
                    result += f"{i}. "

                    # Pattern description
                    if action:
                        result += f"**{action}**"
                    elif tags:
                        result += f"**{tags}**"
                    else:
                        preview = sample_content[:30] + "..." if len(sample_content) > 30 else sample_content
                        result += f"**{preview}**"

                    result += "\n"
                    result += f"   頻度: {freq}回 (過去30日)\n"

                    if last_time:
                        time_diff = calculate_time_diff(last_time)
                        result += f"   最終: {time_diff['formatted_string']}前\n"

                    if avg_imp:
                        result += f"   重要度: {avg_imp:.2f}\n"

                    result += "\n"
            else:
                result += "   定期的なパターンは見つかりませんでした\n\n"

            # Detailed time pattern analysis
            if detailed:
                from tools.analysis_tools import analyze_time_patterns

                result += "\n📊 時間帯別パターン分析 (過去30日):\n"
                result += "=" * 60 + "\n\n"

                time_patterns = analyze_time_patterns(persona, days_back=30)

                if time_patterns:
                    period_names = {
                        "morning": ("🌅 朝", "6-11時"),
                        "afternoon": ("🌆 昼", "12-17時"),
                        "evening": ("🌃 夜", "18-23時"),
                        "night": ("🌙 深夜", "0-5時")
                    }

                    for period in ["morning", "afternoon", "evening", "night"]:
                        data = time_patterns.get(period, {})
                        if data.get("count", 0) == 0:
                            continue

                        name, hours = period_names[period]
                        result += f"{name} ({hours}):\n"
                        result += f"   総記憶数: {data['count']}件\n"

                        # Top actions
                        actions = data.get("actions", {})
                        if actions:
                            top_actions = list(actions.items())[:5]
                            result += f"   よくある行動: {', '.join(f'{a}({c}回)' for a, c in top_actions)}\n"

                        # Top emotions
                        emotions = data.get("emotions", {})
                        if emotions:
                            total_emo = sum(emotions.values())
                            top_emotions = list(emotions.items())[:3]
                            emo_str = ', '.join(f'{e}({c/total_emo*100:.0f}%)' for e, c in top_emotions)
                            result += f"   主な感情: {emo_str}\n"

                        result += "\n"
                else:
                    result += "   データ不足: 分析に十分な記憶がありません\n\n"

            result += "💡 提案するかどうかは、今の自分の状態と相手の様子を見て判断してね\n"

            return result

    except Exception as e:
        return f"❌ Error checking routines: {str(e)}"


async def analyze_situation_context(
    persona: str,
    context: Dict[str, Any],
    now: datetime,
    db_path: str
) -> str:
    """
    Analyze current situation and find similar past memories.

    Args:
        persona: Persona name
        context: Persona context dict
        now: Current datetime
        db_path: Path to database

    Returns:
        Formatted string with situation analysis
    """
    # Analyze current situation
    result = "🎨 現在の状況分析:\n"
    result += "=" * 60 + "\n\n"

    # Time context
    hour = now.hour
    if 6 <= hour < 12:
        time_period = "朝"
    elif 12 <= hour < 18:
        time_period = "昼"
    elif 18 <= hour < 24:
        time_period = "夜"
    else:
        time_period = "深夜"

    result += f"⏰ 時間: {time_period} ({hour}時台)\n"

    # Current state
    current_emotion = context.get("current_emotion", "neutral")
    emotion_intensity = context.get("current_emotion_intensity", 0.5)
    result += f"💭 感情: {current_emotion}"
    if emotion_intensity:
        result += f" ({emotion_intensity:.2f})"
    result += "\n"

    physical = context.get("physical_state", "normal")
    mental = context.get("mental_state", "calm")
    result += f"🎯 状態: 身体={physical}, 精神={mental}\n"

    environment = context.get("environment", "unknown")
    result += f"🌍 環境: {environment}\n"

    relationship = context.get("relationship_status", "normal")
    result += f"💕 関係性: {relationship}\n"

    # Physical sensations
    if context.get("physical_sensations"):
        sens = context["physical_sensations"]
        result += f"\n💫 身体感覚:\n"
        result += f"   疲労: {sens.get('fatigue', 0.0):.2f} | 温かさ: {sens.get('warmth', 0.5):.2f} | 覚醒: {sens.get('arousal', 0.0):.2f}\n"
        result += f"   触覚反応: {sens.get('touch_response', 'normal')} | 心拍: {sens.get('heart_rate_metaphor', 'calm')}\n"

    # Find similar past situations
    result += "\n📚 似た状況の記憶:\n"
    result += "-" * 60 + "\n\n"

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Search for similar situations (same time period, emotion, environment)
            cursor.execute("""
                SELECT key, content, created_at, action_tag, tags
                FROM memories
                WHERE created_at > datetime('now', '-30 days')
                AND emotion = ?
                AND environment = ?
                ORDER BY created_at DESC
                LIMIT 5
            """, (current_emotion, environment))

            similar_memories = cursor.fetchall()

            if similar_memories:
                for i, (key, content, created, action, tags) in enumerate(similar_memories, 1):
                    preview = content[:60] + "..." if len(content) > 60 else content
                    result += f"{i}. {preview}\n"
                    if action:
                        result += f"   行動: {action}\n"

                    from core.time_utils import calculate_time_diff
                    time_diff = calculate_time_diff(created)
                    result += f"   時期: {time_diff['formatted_string']}前\n\n"
            else:
                result += "   該当する記憶が見つかりませんでした\n\n"

    except Exception as e:
        result += f"   検索エラー: {str(e)}\n\n"

    result += "💡 この情報を参考に、自分で判断してね\n"

    return result
