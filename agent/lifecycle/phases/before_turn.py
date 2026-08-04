from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeAlias, cast

from agent.config_models import OptimizationConfig
from agent.optimization.profiles import (
    OPTIMIZATION_PROFILE_METADATA_KEY,
    resolve_optimization_profile,
)
from bus.event_bus import EventBus
from agent.core.runtime_support import SessionLike
from agent.core.types import ContextBundle
from agent.lifecycle.phase import (
    PhaseFrame,
    PhaseModule,
    append_string_exports,
    collect_prefixed_slots,
    topo_sort_modules,
)
from agent.lifecycle.types import BeforeTurnCtx, TurnState

if TYPE_CHECKING:
    from agent.core.passive_turn import ContextStore
    from session.manager import SessionManager


@dataclass
class BeforeTurnFrame(PhaseFrame[TurnState, BeforeTurnCtx]):
    pass


BeforeTurnModules: TypeAlias = list[PhaseModule[BeforeTurnFrame]]


_SESSION_SLOT = "session:session"
_CONTEXT_BUNDLE_SLOT = "session:context_bundle"
_CTX_SLOT = "session:ctx"
_EXTRA_HINT_PREFIX = "session:extra_hint:"
_ABORT_REPLY_SLOT = "session:abort_reply"


class _AcquireSessionModule:
    slot = "before_turn.acquire_session"
    requires: tuple[str, ...] = ()
    produces = (_SESSION_SLOT,)

    def __init__(
        self,
        session_manager: SessionManager,
        *,
        session_metadata_defaults: Mapping[str, object] | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._session_metadata_defaults = dict(session_metadata_defaults or {})

    async def run(self, frame: BeforeTurnFrame) -> BeforeTurnFrame:
        state = frame.input
        session = self._session_manager.get_or_create(state.session_key)
        if self._session_metadata_defaults:
            metadata = (
                getattr(session, "metadata", {})
                if isinstance(getattr(session, "metadata", {}), dict)
                else {}
            )
            changed = False
            for key, value in self._session_metadata_defaults.items():
                if key not in metadata:
                    metadata[key] = value
                    changed = True
            if changed:
                session.metadata = metadata
        state.session = session
        frame.slots[_SESSION_SLOT] = session
        return frame


class _PrepareContextModule:
    slot = "before_turn.prepare_context"
    requires = ("before_turn.acquire_session", _SESSION_SLOT)
    produces = (_CONTEXT_BUNDLE_SLOT,)

    def __init__(
        self,
        context_store: ContextStore,
        *,
        optimization: OptimizationConfig | None = None,
        base_history_window: int = 500,
    ) -> None:
        self._context_store = context_store
        self._optimization = optimization or OptimizationConfig()
        self._base_history_window = max(1, int(base_history_window))

    async def run(self, frame: BeforeTurnFrame) -> BeforeTurnFrame:
        if _CTX_SLOT in frame.slots:
            return frame
        state = frame.input
        session = cast(SessionLike, frame.slots[_SESSION_SLOT])
        msg_metadata = state.msg.metadata if isinstance(state.msg.metadata, dict) else {}
        session_metadata = (
            getattr(session, "metadata", {})
            if isinstance(getattr(session, "metadata", {}), dict)
            else {}
        )
        profile = resolve_optimization_profile(
            self._optimization,
            base_memory_window=self._base_history_window,
            session_metadata=session_metadata,
            msg_metadata=msg_metadata,
        )
        state.extra_metadata[OPTIMIZATION_PROFILE_METADATA_KEY] = profile.name
        state.extra_metadata["optimization_profile_source"] = profile.source
        state.extra_metadata["experiment_tag"] = profile.name
        state.extra_metadata["experiment_overrides"] = dict(profile.overrides)
        bundle = await self._context_store.prepare(
            msg=state.msg,
            session_key=state.session_key,
            session=session,
            history_window=profile.memory_window,
        )
        frame.slots[_CONTEXT_BUNDLE_SLOT] = bundle
        return frame


class _BuildBeforeTurnCtxModule:
    slot = "before_turn.build_ctx"
    requires = ("before_turn.prepare_context", _CONTEXT_BUNDLE_SLOT)
    produces = (_CTX_SLOT,)

    async def run(self, frame: BeforeTurnFrame) -> BeforeTurnFrame:
        if _CTX_SLOT in frame.slots:
            return frame
        state = frame.input
        bundle = cast(ContextBundle, frame.slots[_CONTEXT_BUNDLE_SLOT])
        frame.slots[_CTX_SLOT] = BeforeTurnCtx(
            session_key=state.session_key,
            channel=state.msg.channel,
            chat_id=state.msg.chat_id,
            content=state.msg.content,
            timestamp=state.msg.timestamp,
            skill_names=list(bundle.skill_mentions),
            retrieved_memory_block=bundle.retrieved_memory_block,
            retrieval_trace_raw=bundle.retrieval_trace_raw,
            history_messages=tuple(bundle.history_messages),
        )
        return frame


class _EmitBeforeTurnCtxModule:
    slot = "before_turn.emit"
    requires = ("before_turn.build_ctx", _CTX_SLOT)
    produces = (_CTX_SLOT,)

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def run(self, frame: BeforeTurnFrame) -> BeforeTurnFrame:
        ctx = cast(BeforeTurnCtx, frame.slots[_CTX_SLOT])
        frame.slots[_CTX_SLOT] = await self._bus.emit(ctx)
        return frame


class _ReturnBeforeTurnCtxModule:
    slot = "before_turn.return"
    requires = ("before_turn.collect_exports", _CTX_SLOT)

    async def run(self, frame: BeforeTurnFrame) -> BeforeTurnFrame:
        frame.output = cast(BeforeTurnCtx, frame.slots[_CTX_SLOT])
        return frame


class _CollectBeforeTurnExportSlotsModule:
    slot = "before_turn.collect_exports"
    requires = ("before_turn.emit", _CTX_SLOT)
    produces = (_CTX_SLOT,)

    async def run(self, frame: BeforeTurnFrame) -> BeforeTurnFrame:
        ctx = cast(BeforeTurnCtx, frame.slots[_CTX_SLOT])
        append_string_exports(
            ctx.extra_hints,
            collect_prefixed_slots(frame.slots, _EXTRA_HINT_PREFIX),
        )
        abort_reply = frame.slots.get(_ABORT_REPLY_SLOT)
        if isinstance(abort_reply, str) and abort_reply:
            ctx.abort = True
            ctx.abort_reply = abort_reply
        return frame


def default_before_turn_modules(
    bus: EventBus,
    session_manager: SessionManager,
    context_store: ContextStore,
    *,
    optimization: OptimizationConfig | None = None,
    base_history_window: int = 500,
    session_metadata_defaults: Mapping[str, object] | None = None,
    plugin_modules: BeforeTurnModules | None = None,
) -> BeforeTurnModules:
    builtins: BeforeTurnModules = [
        _AcquireSessionModule(
            session_manager,
            session_metadata_defaults=session_metadata_defaults,
        ),
        _PrepareContextModule(
            context_store,
            optimization=optimization,
            base_history_window=base_history_window,
        ),
        _BuildBeforeTurnCtxModule(),
        _EmitBeforeTurnCtxModule(bus),
        _CollectBeforeTurnExportSlotsModule(),
        _ReturnBeforeTurnCtxModule(),
    ]
    return cast(
        BeforeTurnModules,
        topo_sort_modules(builtins + list(plugin_modules or [])),
    )
