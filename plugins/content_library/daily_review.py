from __future__ import annotations


def build_daily_review_prompt(hours: int = 24) -> str:
    """Build the prompt used by an existing soft scheduler job."""
    bounded_hours = max(1, min(int(hours), 24 * 365))
    return (
        "这是个人内容收藏每日回顾任务。\n"
        f"必须先调用 list_recent_content_items(hours={bounded_hours}, "
        "for_push=true)。\n"
        "如果返回 count=0，直接返回空文本，不要发送或编造内容。\n"
        "如果有内容，只根据工具返回的事实生成简短中文摘要：按主题分组，"
        "列出平台、标题、备注和链接；不要声称看过视频本体。\n"
        "不要调用 message_push；当前任务由调度器负责发送最终文本。\n"
        "不要因为本次摘要自动写入长期记忆。"
    )
