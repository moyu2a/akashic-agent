from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Protocol
from datetime import datetime

from bus.events import OutboundMessage


@dataclass
class OutboundDispatch:
    channel: str
    chat_id: str
    content: str
    thinking: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    media: list[str] = field(default_factory=list)


class OutboundPort(Protocol):
    async def dispatch(self, outbound: OutboundDispatch) -> bool: ...


class BusOutboundPort:
    def __init__(self, bus: Any) -> None:
        self._bus = bus

    async def dispatch(self, outbound: OutboundDispatch) -> bool:
        maybe = self._bus.publish_outbound(
            OutboundMessage(
                channel=outbound.channel,
                chat_id=outbound.chat_id,
                content=outbound.content,
                thinking=outbound.thinking,
                metadata=dict(outbound.metadata or {}),
                media=list(outbound.media or []),
            )
        )
        if inspect.isawaitable(maybe):
            await maybe
        return True


class PersistentOutboundPort:
    def __init__(self, session_manager: Any, delegate: OutboundPort) -> None:
        self._session_manager = session_manager
        self._delegate = delegate

    async def dispatch(self, outbound: OutboundDispatch) -> bool:
        session_key = f"{outbound.channel}:{outbound.chat_id}"
        session = self._session_manager.get_or_create(session_key)
        if not session.messages or str(session.messages[-1].get("content", "")) != str(
            outbound.content or ""
        ):
            session.add_message(
                "assistant",
                str(outbound.content or ""),
                media=list(outbound.media or []) or None,
                thinking=outbound.thinking,
                **dict(outbound.metadata or {}),
            )
            await self._session_manager.append_messages(session, session.messages[-1:])
        message = session.messages[-1] if session.messages else {}
        message_id = str(message.get("id") or "")
        if not message_id:
            message_id = self._session_manager.peek_next_message_id(session_key)
        store = getattr(self._session_manager, "_store")
        outbox = store.enqueue_outbox(
            session_key=session_key,
            message_id=message_id,
            channel=outbound.channel,
            chat_id=outbound.chat_id,
        )
        try:
            sent = await self._delegate.dispatch(outbound)
        except Exception as exc:
            store.mark_outbox_unknown(
                outbox["outbox_id"],
                remote_message_id=message_id,
                error=str(exc),
            )
            return False
        if not sent:
            store.mark_outbox_failed(
                outbox["outbox_id"],
                error="delegate returned false",
            )
            return False
        store.mark_outbox_sent(
            outbox["outbox_id"],
            remote_message_id=message_id,
        )
        return True


class PersistentOutboxReconciler:
    def __init__(self, session_manager: Any, delegate: OutboundPort) -> None:
        self._session_manager = session_manager
        self._delegate = delegate
        self._store = getattr(session_manager, "_store")

    async def flush_pending(
        self,
        *,
        worker_id: str,
        limit: int = 100,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> int:
        current = now or datetime.now().astimezone()
        sent = 0
        while sent < limit:
            outbox = self._store.claim_next_outbox(
                worker_id=worker_id,
                now=current,
                lease_seconds=lease_seconds,
            )
            if outbox is None:
                break
            message = dict(outbox.get("message") or {})
            outbound = OutboundDispatch(
                channel=str(outbox["channel"]),
                chat_id=str(outbox["chat_id"]),
                content=str(message.get("content", "") or ""),
                thinking=message.get("thinking"),
                metadata=dict(message.get("metadata") or {}),
                media=list(message.get("media") or []),
            )
            try:
                accepted = await self._delegate.dispatch(outbound)
            except Exception as exc:
                self._store.mark_outbox_unknown(
                    outbox["outbox_id"],
                    remote_message_id=str(outbox["message_id"]),
                    error=str(exc),
                    now=current,
                )
                sent += 1
                continue
            if not accepted:
                self._store.mark_outbox_failed(
                    outbox["outbox_id"],
                    error="delegate returned false",
                    now=current,
                )
                sent += 1
                continue
            self._store.mark_outbox_sent(
                outbox["outbox_id"],
                remote_message_id=str(outbox["message_id"]),
                now=current,
            )
            sent += 1
        return sent

    async def reconcile_unknown(
        self,
        probe: Any,
        *,
        limit: int = 100,
        now: datetime | None = None,
    ) -> int:
        current = now or datetime.now().astimezone()
        changed = 0
        for outbox in self._store.list_outbox(status="unknown", limit=limit):
            verdict = probe(outbox)
            if verdict is True:
                self._store.mark_outbox_sent(
                    outbox["outbox_id"],
                    remote_message_id=str(outbox.get("remote_message_id") or outbox["message_id"]),
                    now=current,
                )
                changed += 1
            elif verdict is False:
                self._store.mark_outbox_failed(
                    outbox["outbox_id"],
                    error=str(outbox.get("last_error") or "unknown delivery failed"),
                    now=current,
                )
                changed += 1
        return changed


class PushToolOutboundPort:
    def __init__(self, push_tool: Any) -> None:
        self._push = push_tool

    async def dispatch(self, outbound: OutboundDispatch) -> bool:
        message = str(outbound.content or "").strip()
        channel = str(outbound.channel or "").strip()
        chat_id = str(outbound.chat_id or "").strip()
        media = [str(item).strip() for item in outbound.media if str(item).strip()]
        if (not message and not media) or not channel or not chat_id:
            return False
        try:
            result = ""
            if message or media:
                result = await self._push.execute(
                    channel=channel,
                    chat_id=chat_id,
                    message=message,
                    image=media[0] if media else None,
                )
            for image in media[1:]:
                result = await self._push.execute(
                    channel=channel,
                    chat_id=chat_id,
                    image=image,
                )
        except Exception:
            return False
        return "已发送" in str(result)
