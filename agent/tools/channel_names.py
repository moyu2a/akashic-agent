"""Channel name normalization shared by push-like tools."""


def normalize_channel_chat(channel: str, chat_id: str) -> tuple[str, str]:
    normalized_channel = str(channel or "").strip()
    normalized_chat_id = str(chat_id or "").strip()
    if normalized_channel == "qq" and normalized_chat_id.startswith("c2c:"):
        return "qqbot", normalized_chat_id
    return normalized_channel, normalized_chat_id
