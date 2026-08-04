from __future__ import annotations

import logging
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from agent.lifecycle.types import AfterReasoningCtx, BeforeTurnCtx, TurnState
from agent.optimization.profiles import (
    DEFAULT_OPTIMIZATION_PROFILES,
    OPTIMIZATION_PROFILE_METADATA_KEY,
    resolve_optimization_profile,
)
from agent.policies.approved_side_effect_runtime import ApprovedSideEffectRuntime
from agent.policies.approved_shell_side_effect_runtime import (
    ApprovedShellSideEffectRuntime,
)
from agent.policies.approved_side_effect_store import (
    ApprovedSideEffectRecord,
    ApprovedSideEffectStore,
)
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.shell_sandbox_runner import (
    DockerPodmanSandboxRunner,
    SandboxRunner,
)
from agent.policies.side_effect_payload_vault import MANAGED_SIDE_EFFECT_TOOLS
from agent.policies.tool_approval_context import trusted_approval_from_runtime
from agent.policies.tool_approval_decision import ToolApprovalDecision
from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerEvent,
    ToolAuditLedgerQuery,
    ToolAuditLedgerStore,
    open_tool_audit_ledger_fail_open,
    sanitize_tool_audit_metadata,
)
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import (
    ToolApprovalRequestRecord,
    ToolApprovalStore,
)
from agent.tool_hooks import ToolExecutionRequest, ToolExecutor
from agent.plugins import Plugin
from agent.prompting import is_context_frame

logger = logging.getLogger("plugin.status_commands")

_SESSION_SLOT = "session:session"
_CTX_SLOT = "session:ctx"
_REASONING_CTX_SLOT = "reasoning:ctx"
_TS_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})")
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")
_APPROVAL_REMINDER_META_KEY = "approval_choice_reminder"


class MemoryStatusCommandModule:
    slot = "status_commands.memory_status"
    requires = ("before_turn.acquire_session", _SESSION_SLOT)
    produces = (_CTX_SLOT,)

    def __init__(self, plugin_name: str) -> None:
        self._plugin_name = plugin_name

    async def run(self, frame) -> object:
        if _CTX_SLOT in frame.slots:
            return frame
        state = frame.input
        command = _normalize_command(state.msg.content)
        if command not in {
            "/memorystatus",
            "/memory_status",
            "/compact_status",
        }:
            return frame
        session = state.session
        if session is None:
            return frame
        messages = list(getattr(session, "messages", []))
        last = max(0, int(getattr(session, "last_consolidated", 0)))
        last = min(last, len(messages))
        logger.info(
            "[%s:%s] 命中命令: %s",
            self._plugin_name,
            self.__class__.__name__,
            command,
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state, _format_memory_status_reply(messages, last)
        )
        return frame


class KVCacheCommandModule:
    slot = "status_commands.kvcache"
    requires = ("before_turn.acquire_session", _SESSION_SLOT)
    produces = (_CTX_SLOT,)

    def __init__(self, plugin_name: str, db_path: Path | None) -> None:
        self._plugin_name = plugin_name
        self._db_path = db_path

    async def run(self, frame) -> object:
        if _CTX_SLOT in frame.slots:
            return frame
        state = frame.input
        command = _normalize_command(state.msg.content)
        if command not in {"/kvcache", "/cache_status"}:
            return frame
        logger.info(
            "[%s:%s] 命中命令: %s",
            self._plugin_name,
            self.__class__.__name__,
            command,
        )
        reply = self._build_reply(state)
        frame.slots[_CTX_SLOT] = _abort_ctx(state, reply)
        return frame

    def _build_reply(self, state: TurnState) -> str:
        db_path = self._db_path
        if not db_path or not db_path.exists():
            return "暂无 KVCache 数据（observe 数据库不存在）。"

        args = (state.msg.content or "").strip().split()
        limit = 5
        if len(args) > 1:
            try:
                limit = max(1, min(30, int(args[1])))
            except ValueError:
                pass

        try:
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.execute(
                    """SELECT llm_output, ts, react_cache_prompt_tokens, react_cache_hit_tokens
                       FROM turns WHERE session_key=? AND source='agent'
                       ORDER BY id DESC LIMIT ?""",
                    [state.session_key, limit],
                )
                rows = cursor.fetchall()
            finally:
                conn.close()
        except Exception:
            logger.exception("KVCache 查询失败")
            return "KVCache 查询失败。"

        if not rows:
            return "暂无 KVCache 数据。"

        overall_prompt = sum(r[2] or 0 for r in rows)
        overall_hit = sum(r[3] or 0 for r in rows)
        overall_pct = (
            (overall_hit / overall_prompt * 100) if overall_prompt > 0 else 0.0
        )

        lines = [
            f"⚡ KVCache · 最近 {len(rows)} 轮",
            "",
            f"命中率  {overall_pct:.1f}%  {_pct_bar(overall_pct)}",
            f"Token  {overall_hit:,} / {overall_prompt:,}",
        ]
        for row in rows:
            llm_output, ts, prompt_tokens, hit_tokens = row
            content = _content_to_text(llm_output or "")
            if is_context_frame(content):
                content = ""
            preview = _preview_text(content, limit=72)
            hit = hit_tokens or 0
            prompt = prompt_tokens or 0
            pct = (hit / prompt * 100) if prompt > 0 else 0.0
            lines.extend(["", ""])
            lines.append(
                f"{_format_ts(ts)}   {_pct_emoji(pct)} {pct:.1f}%  {_pct_bar(pct)}"
            )
            lines.append(f"    {hit:,} / {prompt:,} tokens")
            if preview:
                lines.append(f"    {preview}")
        return "\n".join(lines)


class UsageCommandModule:
    slot = "status_commands.usage"
    requires = ("before_turn.acquire_session", _SESSION_SLOT)
    produces = (_CTX_SLOT,)

    def __init__(
        self,
        plugin_name: str,
        db_path: Path | None,
        app_config: Any = None,
    ) -> None:
        self._plugin_name = plugin_name
        self._db_path = db_path
        self._app_config = app_config

    async def run(self, frame) -> object:
        if _CTX_SLOT in frame.slots:
            return frame
        state = frame.input
        command = _normalize_command(state.msg.content)
        if command not in {
            "/usage_arch",
            "/usage_experiments",
            "/usage_baseline",
            "/usage_compare",
            "/usage_turn",
            "/usage_tag",
            "/usage_profile",
        }:
            return frame
        logger.info(
            "[%s:%s] 命中命令: %s",
            self._plugin_name,
            self.__class__.__name__,
            command,
        )
        reply = self._build_reply(state)
        frame.slots[_CTX_SLOT] = _abort_ctx(state, reply)
        return frame

    def _build_reply(self, state: TurnState) -> str:
        args = (state.msg.content or "").strip().split()
        command = args[0].lower() if args else ""
        if command == "/usage_arch":
            return self._usage_arch_reply()
        if command == "/usage_tag":
            return self._usage_tag_reply(state, args)
        if command == "/usage_profile":
            return self._usage_profile_reply(state, args)
        if not self._db_path or not self._db_path.exists():
            return "usage: no observe database"
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                if command == "/usage_experiments":
                    return self._usage_experiments_reply(conn)
                if command == "/usage_baseline":
                    limit = _usage_limit(args, default=100)
                    return self._usage_baseline_reply(conn, limit)
                if command == "/usage_compare":
                    if len(args) < 3:
                        return "usage: /usage_compare <tag_a> <tag_b>"
                    return self._usage_compare_reply(conn, args[1], args[2])
                if command == "/usage_turn":
                    if len(args) < 2:
                        return "usage: /usage_turn <turn_id>"
                    return self._usage_turn_reply(conn, args[1])
            finally:
                conn.close()
        except Exception:
            logger.exception("usage 查询失败")
            return "usage: query_failed"
        return "usage: unknown command"

    def _usage_arch_reply(self) -> str:
        cfg = self._app_config
        if cfg is None:
            return "usage arch\nconfig: unavailable\nexperiment default: baseline"
        lines = [
            "usage arch",
            f"model: {_safe_config_value(getattr(cfg, 'model', ''))}",
            f"light_model: {_safe_config_value(getattr(cfg, 'light_model', '')) or 'disabled'}",
            f"max_tokens: {getattr(cfg, 'max_tokens', '-')}",
            f"max_iterations: {getattr(cfg, 'max_iterations', '-')}",
            f"memory_window: {getattr(cfg, 'memory_window', '-')}",
            f"tool_search_enabled: {getattr(cfg, 'tool_search_enabled', '-')}",
            f"optimization.enabled: {getattr(getattr(cfg, 'optimization', None), 'enabled', '-')}",
            f"optimization.default_profile: {getattr(getattr(cfg, 'optimization', None), 'default_profile', '-')}",
            "experiment default: baseline",
            "sensitive fields: hidden",
        ]
        proactive = getattr(cfg, "proactive", None)
        if proactive is not None:
            agent_cfg = getattr(proactive, "agent", None)
            if agent_cfg is not None:
                lines.extend(
                    [
                        f"proactive.max_steps: {getattr(agent_cfg, 'max_steps', '-')}",
                        f"proactive.content_limit: {getattr(agent_cfg, 'content_limit', '-')}",
                    ]
                )
        return "\n".join(lines)

    def _usage_tag_reply(self, state: TurnState, args: list[str]) -> str:
        if len(args) < 2:
            return "usage: /usage_tag <tag>"
        tag = _usage_sanitize_tag(args[1])
        session = state.session
        if session is None:
            return "usage tag: session unavailable"
        metadata = getattr(session, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            try:
                session.metadata = metadata
            except Exception:
                return "usage tag: session metadata unavailable"
        metadata["usage_experiment_tag"] = tag
        return f"usage tag: {tag}"

    def _usage_profile_reply(self, state: TurnState, args: list[str]) -> str:
        session = state.session
        if session is None:
            return "usage profile: session unavailable"
        metadata = getattr(session, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            try:
                session.metadata = metadata
            except Exception:
                return "usage profile: session metadata unavailable"

        if len(args) < 2 or args[1].lower() in {"show", "list", "current"}:
            return self._usage_profile_show_reply(session)

        profile = _usage_profile_name(args[1])
        if profile not in DEFAULT_OPTIMIZATION_PROFILES:
            return (
                "usage profile: unknown profile\n"
                f"available: {', '.join(DEFAULT_OPTIMIZATION_PROFILES)}"
            )

        metadata[OPTIMIZATION_PROFILE_METADATA_KEY] = profile
        metadata["usage_experiment_tag"] = profile
        opt_config = getattr(self._app_config, "optimization", None)
        resolved = resolve_optimization_profile(
            opt_config,
            base_memory_window=getattr(self._app_config, "memory_window", 24),
            session_metadata=metadata,
            msg_metadata={},
        )
        metadata["experiment_overrides"] = dict(resolved.overrides)
        note = (
            "\nnote: optimization disabled by config"
            if opt_config is not None and not bool(getattr(opt_config, "enabled", False))
            else ""
        )
        return f"usage profile: {profile}{note}"

    def _usage_profile_show_reply(self, session: object) -> str:
        metadata = getattr(session, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
        profile = _usage_profile_name(
            metadata.get(OPTIMIZATION_PROFILE_METADATA_KEY, "baseline")
        )
        lines = [
            "usage profile",
            f"current: {profile}",
            f"available: {', '.join(DEFAULT_OPTIMIZATION_PROFILES)}",
        ]
        if self._app_config is not None:
            opt = getattr(self._app_config, "optimization", None)
            if opt is not None:
                lines.append(f"enabled: {getattr(opt, 'enabled', False)}")
                lines.append(
                    f"default_profile: {_usage_sanitize_tag(getattr(opt, 'default_profile', 'baseline'))}"
                )
        return "\n".join(lines)

    def _usage_experiments_reply(self, conn: sqlite3.Connection) -> str:
        rows = conn.execute(
            """
            SELECT COALESCE(experiment_tag, 'baseline') AS tag,
                   COUNT(*) AS n,
                   MAX(ts) AS last_ts
            FROM turns
            WHERE source='agent'
            GROUP BY COALESCE(experiment_tag, 'baseline')
            ORDER BY n DESC, tag ASC
            """
        ).fetchall()
        if not rows:
            return "usage experiments: no data"
        lines = ["usage experiments"]
        for row in rows:
            lines.append(
                f"- {row['tag']}: n={row['n']} last={_format_ts(str(row['last_ts']))}"
            )
        return "\n".join(lines)

    def _usage_baseline_reply(self, conn: sqlite3.Connection, limit: int) -> str:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM turns
                WHERE source='agent'
                  AND COALESCE(experiment_tag, 'baseline')='baseline'
                  AND actual_prompt_tokens_sum IS NOT NULL
                ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (limit,),
        ).fetchall()
        if not rows:
            return "usage baseline: no data"
        return _format_usage_summary("usage baseline", _usage_stats(rows))

    def _usage_compare_reply(
        self,
        conn: sqlite3.Connection,
        tag_a: str,
        tag_b: str,
    ) -> str:
        a_rows = _usage_rows_for_tag(conn, tag_a)
        b_rows = _usage_rows_for_tag(conn, tag_b)
        if not a_rows or not b_rows:
            return (
                "usage compare: insufficient data\n"
                f"{tag_a}: n={len(a_rows)}\n{tag_b}: n={len(b_rows)}"
            )
        a = _usage_stats(a_rows)
        b = _usage_stats(b_rows)
        lines = [
            "usage compare",
            f"{tag_a} -> {tag_b}",
            f"samples: {a['n']} -> {b['n']}",
            "",
        ]
        for metric in (
            "actual_prompt_tokens_sum",
            "actual_completion_tokens_sum",
            "actual_total_tokens_sum",
            "turn_duration_ms",
            "llm_duration_ms_sum",
            "tool_duration_ms_sum",
            "react_iteration_count",
            "tool_error_count",
        ):
            lines.append(_format_metric_delta(metric, a, b))
        lines.append(
            "cache hit rate: "
            f"{a['cache_hit_rate']:.1f}% -> {b['cache_hit_rate']:.1f}% "
            f"({_format_point_delta(b['cache_hit_rate'] - a['cache_hit_rate'])})"
        )
        return "\n".join(lines)

    def _usage_turn_reply(self, conn: sqlite3.Connection, raw_turn_id: str) -> str:
        try:
            turn_id = int(raw_turn_id)
        except ValueError:
            return "usage: /usage_turn <turn_id>"
        row = conn.execute(
            """
            SELECT id, ts, session_key, COALESCE(experiment_tag, 'baseline') AS experiment_tag,
                   actual_prompt_tokens_sum, actual_completion_tokens_sum,
                   actual_total_tokens_sum, actual_cache_hit_tokens_sum,
                   actual_cache_miss_tokens_sum, actual_prompt_tokens_peak,
                   history_tokens, prompt_tokens, react_input_sum_tokens,
                   react_input_peak_tokens, turn_duration_ms, llm_duration_ms_sum,
                   tool_duration_ms_sum, react_iteration_count, exit_reason,
                   tool_error_count, max_iterations_hit, empty_reply,
                   simple_fast_path
            FROM turns
            WHERE id=? AND source='agent'
            """,
            (turn_id,),
        ).fetchone()
        if row is None:
            return "usage turn: not found"
        hit = int(row["actual_cache_hit_tokens_sum"] or 0)
        miss = int(row["actual_cache_miss_tokens_sum"] or 0)
        denom = hit + miss
        hit_rate = (hit / denom * 100) if denom else 0.0
        return "\n".join(
            [
                f"usage turn #{row['id']}",
                f"ts: {_format_ts(str(row['ts']))}",
                f"session: {_usage_session_kind(str(row['session_key']))}",
                f"experiment: {row['experiment_tag']}",
                f"actual prompt/completion/total: {row['actual_prompt_tokens_sum'] or 0:,} / {row['actual_completion_tokens_sum'] or 0:,} / {row['actual_total_tokens_sum'] or 0:,}",
                f"actual cache hit/miss/rate: {hit:,} / {miss:,} / {hit_rate:.1f}%",
                f"estimated history/prompt/react_sum: {row['history_tokens'] or 0:,} / {row['prompt_tokens'] or 0:,} / {row['react_input_sum_tokens'] or 0:,}",
                f"duration turn/llm/tool: {row['turn_duration_ms'] or 0:,} / {row['llm_duration_ms_sum'] or 0:,} / {row['tool_duration_ms_sum'] or 0:,} ms",
                f"iterations: {row['react_iteration_count'] or 0}",
                f"simple_fast_path: {row['simple_fast_path'] or 0}",
                f"exit: {row['exit_reason'] or 'unknown'}",
                f"tool_errors: {row['tool_error_count'] or 0}",
            ]
        )


class ToolApprovalCommandModule:
    slot = "status_commands.tool_approval"
    requires = ("before_turn.acquire_session", _SESSION_SLOT)
    produces = (_CTX_SLOT,)

    def __init__(
        self,
        plugin_name: str,
        approval_store: ToolApprovalStore,
        *,
        workspace: Path | None = None,
        side_effect_store: ApprovedSideEffectStore | None = None,
        side_effect_vault: SideEffectPayloadVault | None = None,
        audit_ledger_store: ToolAuditLedgerStore | None = None,
        shell_sandbox_runner: SandboxRunner | None = None,
        task_execution_service: Any = None,
        tool_registry: Any = None,
    ) -> None:
        self._plugin_name = plugin_name
        self._approval_store = approval_store
        self._workspace = workspace.expanduser().resolve() if workspace else None
        self._side_effect_store = side_effect_store
        self._side_effect_vault = side_effect_vault
        self._audit_ledger_store = audit_ledger_store
        self._shell_sandbox_runner = shell_sandbox_runner
        self._task_execution_service = task_execution_service
        self._tool_registry = tool_registry

    async def run(self, frame) -> object:
        if _CTX_SLOT in frame.slots:
            return frame
        state = frame.input
        command = _normalize_command(state.msg.content)
        if command == "/approvals":
            return self._handle_list(frame, state)
        if command == "/approve_tool":
            return self._handle_approve(frame, state)
        if command == "/approve_last":
            return await self._handle_approve_last(frame, state)
        if command == "/deny_tool":
            return self._handle_deny(frame, state)
        if command == "/prepare_tool":
            return self._handle_prepare(frame, state)
        if command == "/run_approved_tool":
            return await self._handle_run_approved(frame, state)
        if command == "/rollback_tool":
            return self._handle_rollback(frame, state)
        if command == "/tool_audit":
            return self._handle_tool_audit(frame, state)
        choice = _numeric_approval_choice(state.msg.content)
        if choice:
            return await self._handle_numeric_choice(frame, state, choice)
        return frame

    def _handle_list(self, frame, state: TurnState) -> object:
        logger.info(
            "[%s:%s] 命中命令: /approvals",
            self._plugin_name,
            self.__class__.__name__,
        )
        now = _approval_now()
        approval_runtime = self._approval_runtime()
        expired = approval_runtime.expire_pending_requests()
        records = self._approval_store.list_pending_requests(
            session_key=state.session_key,
            now=now,
        )
        lines = ["Tool approvals"]
        if expired:
            lines.append(f"expired: {len(expired)}")
        if not records:
            lines.append("pending: none")
        for index, record in enumerate(records):
            lines.extend(
                [
                    "",
                    _format_approval_record(
                        record,
                        current=index == 0,
                        position=index + 1,
                        total=len(records),
                    ),
                ]
            )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            "\n".join(lines),
            approval_lifecycle=_approval_lifecycle_from_decisions(
                self._approval_store,
                expired,
            ),
        )
        return frame

    def _handle_approve(self, frame, state: TurnState) -> object:
        logger.info(
            "[%s:%s] 命中命令: /approve_tool",
            self._plugin_name,
            self.__class__.__name__,
        )
        approval_request_id = _approval_command_id(state.msg.content)
        decision = self._approve_or_reject(
            state=state,
            approval_request_id=approval_request_id,
            action="approve",
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_approval_decision(decision),
            approval_lifecycle=_approval_lifecycle_from_decisions(
                self._approval_store,
                [decision],
                actor="status_command",
            ),
        )
        return frame

    async def _handle_approve_last(self, frame, state: TurnState) -> object:
        logger.info(
            "[%s:%s] 命中命令: /approve_last",
            self._plugin_name,
            self.__class__.__name__,
        )
        pending = self._approval_store.list_pending_requests(
            session_key=state.session_key,
            now=_approval_now(),
        )
        if not pending:
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: not_found\nreason: pending_approval_not_found",
            )
            return frame
        record = pending[-1]
        await self._handle_approve_and_run_record(frame, state, record)
        return frame

    async def _handle_approve_and_run_record(
        self,
        frame,
        state: TurnState,
        record: ToolApprovalRequestRecord,
        *,
        allow_unsupported_approval: bool = False,
    ) -> ToolApprovalDecision:
        unsupported_reason = self._approve_last_unsupported_reason(record)
        if unsupported_reason and not allow_unsupported_approval:
            decision = ToolApprovalDecision(
                action="not_applicable",
                reason=unsupported_reason,
                approval_request_id=record.approval_request_id,
                request_id=record.request_id,
                session_key=record.session_key,
                tool_name=record.tool_name,
                approval_scope=record.approval_scope,
                args_hash=record.args_hash,
            )
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "\n".join(
                    [
                        "status: error",
                        f"reason: {unsupported_reason}",
                        f"id: {record.approval_request_id}",
                        f"tool: {record.tool_name}",
                        "next: use /approve_tool <id> then /run_approved_tool <id>",
                    ]
                ),
            )
            return decision
        if unsupported_reason:
            decision = self._approve_or_reject(
                state=state,
                approval_request_id=record.approval_request_id,
                action="approve",
            )
            reply = _format_approval_decision(decision)
            if decision.action == "approved":
                reply = "\n".join(
                    [
                        reply,
                        f"next: /prepare_tool {record.approval_request_id}",
                        f"next: /run_approved_tool {record.approval_request_id}",
                    ]
                )
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                reply,
                approval_lifecycle=_approval_lifecycle_from_decisions(
                    self._approval_store,
                    [decision],
                    actor="status_command",
                ),
            )
            return decision
        decision = self._approve_or_reject(
            state=state,
            approval_request_id=record.approval_request_id,
            action="approve",
        )
        if decision.action != "approved":
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                _format_approval_decision(decision),
                approval_lifecycle=_approval_lifecycle_from_decisions(
                    self._approval_store,
                    [decision],
                    actor="status_command",
                ),
            )
            return decision
        await self._handle_run_approved_deferred_tool(
            frame,
            state,
            record.approval_request_id,
        )
        ctx = frame.slots.get(_CTX_SLOT)
        if ctx is not None:
            ctx.abort_reply = "\n".join(
                [
                    f"tool: {record.tool_name}",
                    f"id: {record.approval_request_id}",
                    ctx.abort_reply,
                ]
            )
        return decision

    def _approve_last_unsupported_reason(
        self,
        record: ToolApprovalRequestRecord,
    ) -> str:
        if record.tool_name in MANAGED_SIDE_EFFECT_TOOLS:
            return "approve_last_unsupported_tool"
        if record.risk != "write":
            return "approve_last_unsupported_risk"
        if self._side_effect_vault is None:
            return "approve_last_payload_vault_unavailable"
        payload = self._side_effect_vault.get_deferred_tool_payload(
            record.approval_request_id
        )
        if payload is None or not _payload_matches_approval_record(payload, record):
            return "approve_last_payload_unavailable"
        registry = self._tool_registry
        metadata_getter = getattr(registry, "get_invocation_metadata", None)
        executor_getter = getattr(registry, "execute", None)
        if not callable(metadata_getter) or not callable(executor_getter):
            return "approve_last_tool_registry_unavailable"
        metadata = cast(dict[str, object], metadata_getter(record.tool_name))
        if not bool(metadata.get("registered")):
            return "approve_last_tool_not_registered"
        registry_risk = str(metadata.get("registry_risk") or "unknown")
        if registry_risk != record.risk:
            return "approve_last_tool_risk_mismatch"
        return ""

    async def _handle_numeric_choice(
        self,
        frame,
        state: TurnState,
        choice: str,
    ) -> object:
        record = self._current_pending_request(state.session_key)
        if record is None:
            return frame

        if choice == "1":
            decision = await self._handle_approve_and_run_record(
                frame,
                state,
                record,
                allow_unsupported_approval=True,
            )
            if decision.action == "approved":
                _append_pending_progress(frame, self._pending_requests(state.session_key))
            return frame

        if choice == "2":
            decision = self._approve_or_reject(
                state=state,
                approval_request_id=record.approval_request_id,
                action="deny",
                reason="numeric_choice_denied",
            )
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                _format_approval_decision(decision),
                approval_lifecycle=_approval_lifecycle_from_decisions(
                    self._approval_store,
                    [decision],
                    actor="status_command",
                ),
            )
            if decision.action == "denied":
                _append_pending_progress(frame, self._pending_requests(state.session_key))
            return frame

        return self._handle_list(frame, state)

    def _pending_requests(
        self,
        session_key: str,
    ) -> list[ToolApprovalRequestRecord]:
        return self._approval_store.list_pending_requests(
            session_key=session_key,
            now=_approval_now(),
        )

    def _current_pending_request(
        self,
        session_key: str,
    ) -> ToolApprovalRequestRecord | None:
        pending = self._pending_requests(session_key)
        return pending[0] if pending else None

    def _handle_deny(self, frame, state: TurnState) -> object:
        logger.info(
            "[%s:%s] 命中命令: /deny_tool",
            self._plugin_name,
            self.__class__.__name__,
        )
        approval_request_id = _approval_command_id(state.msg.content)
        reason = _bounded_denial_reason(state.msg.content)
        decision = self._approve_or_reject(
            state=state,
            approval_request_id=approval_request_id,
            action="deny",
            reason=reason,
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_approval_decision(decision),
            approval_lifecycle=_approval_lifecycle_from_decisions(
                self._approval_store,
                [decision],
                actor="status_command",
            ),
        )
        return frame

    def _handle_prepare(self, frame, state: TurnState) -> object:
        approval_request_id = _approval_command_id(state.msg.content)
        runtime = self._managed_side_effect_runtime(approval_request_id)
        if runtime is None:
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: "
                f"{self._managed_side_effect_unavailable_reason(approval_request_id)}",
            )
            return frame
        result = runtime.prepare(
            approval_request_id=approval_request_id,
            session_key=state.session_key,
            actor="status_command",
            workspace_root=cast(Path, self._workspace),
            resource_roots=(str(self._workspace),),
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_side_effect_result(
                result.reason, result.message, getattr(result, "diff_text", "")
            ),
            approved_side_effect_lifecycle=self._side_effect_lifecycle(
                approval_request_id
            ),
        )
        return frame

    async def _handle_run_approved(self, frame, state: TurnState) -> object:
        approval_request_id = _approval_command_id(state.msg.content)
        runtime = self._managed_side_effect_runtime(approval_request_id)
        if runtime is None:
            return await self._handle_run_approved_deferred_tool(
                frame, state, approval_request_id
            )
        result = runtime.apply(
            approval_request_id=approval_request_id,
            session_key=state.session_key,
            actor="status_command",
            workspace_root=cast(Path, self._workspace),
            resource_roots=(str(self._workspace),),
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_side_effect_result(result.reason, result.message),
            approved_side_effect_lifecycle=self._side_effect_lifecycle(
                approval_request_id
            ),
        )
        return frame

    async def _handle_run_approved_deferred_tool(
        self,
        frame,
        state: TurnState,
        approval_request_id: str,
    ) -> object:
        record = self._approval_store.get_request(approval_request_id)
        reason = self._approved_tool_unavailable_reason(record, state.session_key)
        if reason:
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                f"status: error\nreason: {reason}",
            )
            return frame
        assert record is not None
        assert self._side_effect_vault is not None
        payload = self._side_effect_vault.get_deferred_tool_payload(approval_request_id)
        if payload is None or not _payload_matches_approval_record(payload, record):
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: approved_tool_payload_unavailable",
            )
            return frame
        registry = self._tool_registry
        metadata_getter = getattr(registry, "get_invocation_metadata", None)
        executor_getter = getattr(registry, "execute", None)
        if not callable(metadata_getter) or not callable(executor_getter):
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: approved_tool_registry_unavailable",
            )
            return frame
        metadata = cast(dict[str, object], metadata_getter(record.tool_name))
        if not bool(metadata.get("registered")):
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: approved_tool_not_registered",
            )
            return frame
        registry_risk = str(metadata.get("registry_risk") or "unknown")
        if registry_risk != record.risk:
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: approved_tool_risk_mismatch",
            )
            return frame
        trusted = trusted_approval_from_runtime(
            approval_request_id=record.approval_request_id,
            actor="status_command",
            source="status_command",
        )

        async def invoke(tool_name: str, arguments: dict[str, Any]) -> object:
            return await executor_getter(tool_name, arguments)

        result = await ToolExecutor(
            approval_runtime=self._approval_runtime(),
            audit_ledger_store=self._audit_ledger_store,
        ).execute(
            ToolExecutionRequest(
                call_id=record.request_id,
                tool_name=record.tool_name,
                arguments=dict(payload.arguments),
                source=_tool_source_from_record(record.source),
                session_key=record.session_key,
                channel=record.channel,
                chat_id=record.chat_id,
                registered=True,
                registry_risk=registry_risk,
                registry_capabilities=_registry_capabilities(
                    metadata.get("registry_capabilities")
                ),
                resource_roots=(str(self._workspace),) if self._workspace else (),
                trusted_approval_context=trusted,
            ),
            invoke,
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_approved_tool_execution_result(result),
            approval_lifecycle=result.approval_lifecycle,
        )
        return frame

    def _handle_rollback(self, frame, state: TurnState) -> object:
        approval_request_id = _approval_command_id(state.msg.content)
        runtime = self._managed_side_effect_runtime(approval_request_id)
        if runtime is None:
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: "
                f"{self._managed_side_effect_unavailable_reason(approval_request_id)}",
            )
            return frame
        result = runtime.rollback(
            approval_request_id=approval_request_id,
            session_key=state.session_key,
            actor="status_command",
            workspace_root=cast(Path, self._workspace),
            resource_roots=(str(self._workspace),),
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_side_effect_result(result.reason, result.message),
            approved_side_effect_lifecycle=self._side_effect_lifecycle(
                approval_request_id
            ),
        )
        return frame

    def _handle_tool_audit(self, frame, state: TurnState) -> object:
        logger.info(
            "[%s:%s] 命中命令: /tool_audit",
            self._plugin_name,
            self.__class__.__name__,
        )
        if self._audit_ledger_store is None:
            frame.slots[_CTX_SLOT] = _abort_ctx(state, "Tool audit ledger unavailable.")
            return frame
        query = _tool_audit_query_from_command(
            state.msg.content,
            session_key=state.session_key,
        )
        events = self._audit_ledger_store.query_events(query)
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_tool_audit_events(events),
        )
        return frame

    def _side_effect_runtime(self) -> ApprovedSideEffectRuntime | None:
        if (
            self._workspace is None
            or self._side_effect_store is None
            or self._side_effect_vault is None
        ):
            return None
        return ApprovedSideEffectRuntime(
            approval_runtime=self._approval_runtime(),
            side_effect_store=self._side_effect_store,
            task_execution_service=self._task_execution_service,
            audit_ledger_store=self._audit_ledger_store,
        )

    def _shell_side_effect_runtime(self) -> ApprovedShellSideEffectRuntime | None:
        if (
            self._workspace is None
            or self._side_effect_store is None
            or self._side_effect_vault is None
        ):
            return None
        return ApprovedShellSideEffectRuntime(
            approval_runtime=self._approval_runtime(),
            side_effect_store=self._side_effect_store,
            sandbox_runner=self._shell_sandbox_runner,
            audit_ledger_store=self._audit_ledger_store,
        )

    def _approval_runtime(self) -> ToolApprovalRuntime:
        return ToolApprovalRuntime(
            self._approval_store,
            side_effect_vault=self._side_effect_vault,
            audit_ledger_store=self._audit_ledger_store,
        )

    def _managed_side_effect_runtime(self, approval_request_id: str) -> object | None:
        record = self._approval_store.get_request(approval_request_id)
        if record is None:
            return self._side_effect_runtime()
        if record.tool_name in {"write_file", "edit_file"}:
            return self._side_effect_runtime()
        if record.tool_name == "shell":
            return self._shell_side_effect_runtime()
        return None

    def _managed_side_effect_unavailable_reason(self, approval_request_id: str) -> str:
        record = self._approval_store.get_request(approval_request_id)
        if record is not None and record.tool_name not in {
            "write_file",
            "edit_file",
            "shell",
        }:
            return "managed_side_effect_tool_unsupported"
        return "approved_side_effect_runtime_unavailable"

    def _approved_tool_unavailable_reason(
        self,
        record: ToolApprovalRequestRecord | None,
        session_key: str,
    ) -> str:
        if record is None:
            return "approval_request_not_found"
        if record.session_key != session_key:
            return "approval_request_not_found"
        if record.status != "approved":
            return f"approval_status_{record.status}"
        if record.tool_name in MANAGED_SIDE_EFFECT_TOOLS:
            return "approved_side_effect_runtime_unavailable"
        if record.risk != "write":
            return "approved_tool_risk_unsupported"
        if self._side_effect_vault is None:
            return "approved_tool_payload_vault_unavailable"
        return ""

    def _side_effect_lifecycle(
        self, approval_request_id: str
    ) -> list[dict[str, object]]:
        if self._side_effect_store is None:
            return []
        record = self._side_effect_store.get_by_approval_id(approval_request_id)
        return [_side_effect_lifecycle_event(record)] if record is not None else []

    def _approve_or_reject(
        self,
        *,
        state: TurnState,
        approval_request_id: str,
        action: str,
        reason: str = "",
    ) -> ToolApprovalDecision:
        now = _approval_now()
        self._approval_runtime().expire_pending_requests()
        if not approval_request_id:
            return ToolApprovalDecision(
                action="not_found",
                reason="approval_request_id_missing",
                session_key=state.session_key,
            )
        record = self._approval_store.get_request(approval_request_id)
        if record is None or record.session_key != state.session_key:
            return ToolApprovalDecision(
                action="not_found",
                reason="approval_request_not_found",
                approval_request_id=approval_request_id,
                session_key=state.session_key,
            )
        if record.status != "pending":
            return ToolApprovalDecision(
                action=record.status,
                reason=f"approval_status_{record.status}",
                approval_request_id=record.approval_request_id,
                request_id=record.request_id,
                session_key=record.session_key,
                tool_name=record.tool_name,
                approval_scope=record.approval_scope,
                args_hash=record.args_hash,
            )
        if _approval_expired(record, now):
            self._approval_runtime().expire_pending_requests()
            expired = self._approval_store.get_request(approval_request_id)
            if expired is not None:
                return ToolApprovalDecision(
                    action=expired.status,
                    reason=f"approval_status_{expired.status}",
                    approval_request_id=expired.approval_request_id,
                    request_id=expired.request_id,
                    session_key=expired.session_key,
                    tool_name=expired.tool_name,
                    approval_scope=expired.approval_scope,
                    args_hash=expired.args_hash,
                )
        if action == "approve":
            return self._approval_runtime().approve_request(
                approval_request_id=record.approval_request_id,
                session_key=record.session_key,
                actor="status_command",
            )
        return self._approval_runtime().deny_request(
            approval_request_id=record.approval_request_id,
            session_key=record.session_key,
            actor="status_command",
            reason=reason or "user_denied",
        )


class StatusCommands(Plugin):
    name = "status_commands"

    def telegram_bot_commands(self) -> list[tuple[str, str]]:
        return [
            ("memorystatus", "查看记忆整理状态"),
            ("kvcache", "查看 KVCache 状态"),
            ("usage_baseline", "查看成本/时延基线"),
            ("usage_experiments", "查看成本/时延实验"),
            ("usage_profile", "查看或切换优化 profile"),
            ("approvals", "查看待审批工具调用"),
            ("tool_audit", "查看工具治理审计记录"),
        ]

    def before_turn_modules(self) -> list[object]:
        plugin_name = self.name or "status_commands"
        db_path = None
        approval_store = None
        side_effect_store = None
        side_effect_vault = None
        audit_ledger_store = None
        if self.context.workspace is not None:
            db_path = self.context.workspace / "observe" / "observe.db"
            approval_store = ToolApprovalStore(
                ToolApprovalRuntime.approval_db_path_from_workspace(
                    self.context.workspace
                )
            )
            side_effect_store = ApprovedSideEffectStore(
                ApprovedSideEffectStore.db_path_from_workspace(self.context.workspace)
            )
            side_effect_vault = ToolApprovalRuntime.side_effect_vault_from_workspace(
                self.context.workspace
            )
            audit_ledger_store = open_tool_audit_ledger_fail_open(
                self.context.workspace,
                logger,
            )
        task_execution_service = getattr(
            self.context,
            "task_execution_service",
            None,
        )
        modules: list[object] = [
            MemoryStatusCommandModule(plugin_name),
            KVCacheCommandModule(plugin_name, db_path),
            UsageCommandModule(
                plugin_name,
                db_path,
                app_config=getattr(self.context, "app_config", None),
            ),
        ]
        if approval_store is not None:
            modules.append(
                ToolApprovalCommandModule(
                    plugin_name,
                    approval_store,
                    workspace=self.context.workspace,
                    side_effect_store=side_effect_store,
                    side_effect_vault=side_effect_vault,
                    audit_ledger_store=audit_ledger_store,
                    shell_sandbox_runner=DockerPodmanSandboxRunner.find_available(),
                    task_execution_service=task_execution_service,
                    tool_registry=getattr(self.context, "tool_registry", None),
                )
            )
        return cast(
            "list[object]",
            modules,
        )

    def after_reasoning_modules(self) -> list[object]:
        if self.context.workspace is None:
            return []
        plugin_name = self.name or "status_commands"
        approval_store = ToolApprovalStore(
            ToolApprovalRuntime.approval_db_path_from_workspace(
                self.context.workspace
            )
        )
        return [ApprovalReminderAfterReasoningModule(plugin_name, approval_store)]


class ApprovalReminderAfterReasoningModule:
    slot = "status_commands.approval_reminder"
    requires = ("after_reasoning.emit", _REASONING_CTX_SLOT)
    produces = (_REASONING_CTX_SLOT,)

    def __init__(
        self,
        plugin_name: str,
        approval_store: ToolApprovalStore,
    ) -> None:
        self._plugin_name = plugin_name
        self._approval_store = approval_store

    async def run(self, frame) -> object:
        ctx = frame.slots.get(_REASONING_CTX_SLOT)
        if not isinstance(ctx, AfterReasoningCtx):
            return frame
        state = frame.input.state
        session = state.session
        if session is None:
            return frame
        metadata = getattr(session, "metadata", None)
        if not isinstance(metadata, dict):
            return frame

        records = self._approval_store.list_pending_requests(
            session_key=state.session_key,
            now=_approval_now(),
        )
        if not records:
            metadata.pop(_APPROVAL_REMINDER_META_KEY, None)
            return frame

        record = records[0]
        requested_ids = _requested_approval_ids(ctx.tool_chain)
        reminder_state = metadata.get(_APPROVAL_REMINDER_META_KEY)
        if not isinstance(reminder_state, dict):
            reminder_state = {}

        if record.approval_request_id in requested_ids:
            if "审批按顺序逐项处理" not in ctx.reply:
                ctx.reply = _append_approval_choice_block(
                    ctx.reply,
                    record,
                    len(records),
                )
            metadata[_APPROVAL_REMINDER_META_KEY] = {
                "approval_id": record.approval_request_id,
                "reminded": False,
            }
            return frame

        if (
            reminder_state.get("approval_id") == record.approval_request_id
            and reminder_state.get("reminded") is True
        ):
            return frame

        ctx.reply = _append_approval_light_reminder(
            ctx.reply,
            len(records),
            record,
        )
        metadata[_APPROVAL_REMINDER_META_KEY] = {
            "approval_id": record.approval_request_id,
            "reminded": True,
        }
        logger.info(
            "[%s:%s] added pending approval reminder for session %s",
            self._plugin_name,
            self.__class__.__name__,
            state.session_key,
        )
        return frame


_USAGE_TAG_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def _usage_sanitize_tag(raw: object) -> str:
    text = _USAGE_TAG_RE.sub("_", str(raw or "baseline").strip())[:64].strip("_")
    return text or "baseline"


def _usage_profile_name(raw: object) -> str:
    return _usage_sanitize_tag(raw).lower().replace("-", "_")


def _usage_limit(args: list[str], *, default: int) -> int:
    if len(args) < 2:
        return default
    try:
        return max(1, min(500, int(args[1])))
    except ValueError:
        return default


def _usage_rows_for_tag(
    conn: sqlite3.Connection,
    tag: str,
    *,
    limit: int = 500,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM turns
            WHERE source='agent'
              AND COALESCE(experiment_tag, 'baseline')=?
              AND actual_prompt_tokens_sum IS NOT NULL
            ORDER BY id DESC LIMIT ?
        ) ORDER BY id ASC
        """,
        (_usage_sanitize_tag(tag), limit),
    ).fetchall()


def _usage_stats(rows: list[sqlite3.Row]) -> dict[str, float]:
    metrics = (
        "actual_prompt_tokens_sum",
        "actual_completion_tokens_sum",
        "actual_total_tokens_sum",
        "turn_duration_ms",
        "llm_duration_ms_sum",
        "tool_duration_ms_sum",
        "react_iteration_count",
        "tool_error_count",
    )
    stats: dict[str, float] = {"n": float(len(rows))}
    for metric in metrics:
        values = [float(row[metric] or 0) for row in rows]
        stats[f"{metric}.avg"] = sum(values) / len(values) if values else 0.0
        stats[f"{metric}.p50"] = _usage_percentile(values, 0.5)
        stats[f"{metric}.p90"] = _usage_percentile(values, 0.9)
        stats[f"{metric}.max"] = max(values, default=0.0)
    hit = sum(float(row["actual_cache_hit_tokens_sum"] or 0) for row in rows)
    miss = sum(float(row["actual_cache_miss_tokens_sum"] or 0) for row in rows)
    if hit == 0 and miss == 0:
        hit = sum(float(row["react_cache_hit_tokens"] or 0) for row in rows)
        prompt = sum(float(row["react_cache_prompt_tokens"] or 0) for row in rows)
        miss = max(0.0, prompt - hit)
    stats["cache_hit_rate"] = (hit / (hit + miss) * 100) if (hit + miss) else 0.0
    return stats


def _usage_percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * q))
    return ordered[index]


def _format_usage_summary(title: str, stats: dict[str, float]) -> str:
    lines = [title, f"samples: {int(stats['n'])}"]
    for metric in (
        "actual_prompt_tokens_sum",
        "actual_completion_tokens_sum",
        "actual_total_tokens_sum",
        "turn_duration_ms",
        "llm_duration_ms_sum",
        "tool_duration_ms_sum",
        "react_iteration_count",
    ):
        lines.append(
            f"{metric}: avg={stats[f'{metric}.avg']:,.1f} "
            f"p50={stats[f'{metric}.p50']:,.0f} "
            f"p90={stats[f'{metric}.p90']:,.0f} "
            f"max={stats[f'{metric}.max']:,.0f}"
        )
    lines.append(f"cache hit rate: {stats['cache_hit_rate']:.1f}%")
    return "\n".join(lines)


def _format_metric_delta(
    metric: str,
    before: dict[str, float],
    after: dict[str, float],
) -> str:
    a = before[f"{metric}.avg"]
    b = after[f"{metric}.avg"]
    return (
        f"{metric}: {a:,.1f} -> {b:,.1f} "
        f"({_format_pct_delta(a, b)})"
    )


def _format_pct_delta(before: float, after: float) -> str:
    if before == 0:
        return "+inf" if after else "0.0%"
    return f"{((after - before) / before * 100):+.1f}%"


def _format_point_delta(delta: float) -> str:
    return f"{delta:+.1f}pt"


def _safe_config_value(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    lowered = text.lower()
    if any(marker in lowered for marker in ("sk-", "secret", "token", "key")):
        return "<hidden>"
    return text


def _usage_session_kind(session_key: str) -> str:
    if session_key.startswith("qqbot:"):
        return "qqbot:*"
    if session_key.startswith("scheduler:"):
        return "scheduler:*"
    if session_key.startswith("cli:"):
        return "cli:*"
    return session_key.split(":", 1)[0] + ":*" if ":" in session_key else session_key


def _normalize_command(content: str) -> str:
    parts = (content or "").strip().split(maxsplit=1)
    if not parts:
        return ""
    head = parts[0].lower()
    if "@" in head:
        head = head.split("@", 1)[0]
    return head


def _numeric_approval_choice(content: str) -> str:
    value = (content or "").strip()
    return value if value in {"1", "2", "3"} else ""


def _requested_approval_ids(
    tool_chain: tuple[dict[str, Any], ...],
) -> set[str]:
    ids: set[str] = set()
    for group in tool_chain:
        calls = group.get("calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            _collect_approval_ids_from_lifecycle(call.get("approval_lifecycle"), ids)
            _collect_approval_ids_from_tool_result(call.get("result"), ids)
    return ids


def _collect_approval_ids_from_lifecycle(
    lifecycle: object,
    ids: set[str],
) -> None:
    if not isinstance(lifecycle, list):
        return
    for event in lifecycle:
        if not isinstance(event, dict):
            continue
        approval_id = event.get("approval_request_id")
        status = str(event.get("status") or "")
        if isinstance(approval_id, str) and approval_id and status == "pending":
            ids.add(approval_id)


def _collect_approval_ids_from_tool_result(result: object, ids: set[str]) -> None:
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError, json.JSONDecodeError):
            return
    else:
        parsed = result
    if not isinstance(parsed, dict):
        return
    approval_request = parsed.get("approval_request")
    if not isinstance(approval_request, dict):
        return
    approval_id = approval_request.get("approval_request_id")
    if isinstance(approval_id, str) and approval_id:
        ids.add(approval_id)


def _append_approval_choice_block(
    reply: str,
    record: ToolApprovalRequestRecord,
    count: int,
) -> str:
    return _append_reply_block(
        reply,
        "\n".join(
            [
                "",
                f"当前处理第 1/{max(1, count)} 项：{record.tool_name}",
                "审批按顺序逐项处理，不会一次批准全部待审批操作。",
                "可回复 1 批准当前项、2 拒绝当前项、3 查看详情。",
                _format_approval_actions(record),
            ]
        ),
    )


def _append_approval_light_reminder(
    reply: str,
    count: int,
    record: ToolApprovalRequestRecord,
) -> str:
    count = max(1, count)
    return _append_reply_block(
        reply,
        "\n".join(
            [
                f"还有 {count} 个待审批操作，当前项：{record.tool_name}。",
                "可回复 1 批准当前项、2 拒绝当前项、3 查看详情。",
            ]
        ),
    )


def _append_reply_block(reply: str, block: str) -> str:
    reply = str(reply or "").rstrip()
    block = str(block or "").strip()
    if not reply:
        return block
    return f"{reply}\n\n{block}"


def _append_pending_progress(
    frame,
    records: list[ToolApprovalRequestRecord],
) -> None:
    ctx = frame.slots.get(_CTX_SLOT)
    if ctx is None:
        return
    if records:
        progress = "\n".join(
            [
                "本次只处理当前项。",
                f"剩余待审批 {len(records)} 项。",
                f"下一项：{records[0].tool_name}",
                "可回复 1 批准当前项、2 拒绝当前项、3 查看详情。",
            ]
        )
    else:
        progress = "\n".join(
            [
                "本次只处理当前项。",
                "当前 session 已无待审批操作。",
            ]
        )
    ctx.abort_reply = _append_reply_block(ctx.abort_reply, progress)


def _approval_command_id(content: str) -> str:
    parts = (content or "").strip().split()
    if len(parts) < 2:
        return ""
    return parts[1]


def _bounded_denial_reason(content: str) -> str:
    parts = (content or "").strip().split(maxsplit=2)
    if len(parts) < 3:
        return "user_denied"
    reason = " ".join(parts[2].split())
    if not reason:
        return "user_denied"
    lower = reason.lower()
    sensitive_markers = (
        "rm ",
        "command",
        "content",
        "token",
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "bearer",
        "private_key",
        "ssh-key",
    )
    if any(marker in lower for marker in sensitive_markers):
        return "user_denied"
    return reason[:80]


def _approval_now() -> datetime:
    return datetime.now(UTC)


def _approval_expired(record: ToolApprovalRequestRecord, now: datetime) -> bool:
    try:
        expires_at = datetime.fromisoformat(record.expires_at)
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now.astimezone(UTC)


def _payload_matches_approval_record(
    payload: Any,
    record: ToolApprovalRequestRecord,
) -> bool:
    payload_record = getattr(payload, "record", None)
    if payload_record is None:
        return False
    return (
        getattr(payload_record, "approval_request_id", "") == record.approval_request_id
        and getattr(payload_record, "request_id", "") == record.request_id
        and getattr(payload_record, "session_key", "") == record.session_key
        and getattr(payload_record, "tool_name", "") == record.tool_name
        and getattr(payload_record, "approval_scope", "") == record.approval_scope
        and getattr(payload_record, "args_hash", "") == record.args_hash
    )


def _registry_capabilities(value: object) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset({value}) if value else frozenset()
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(item for item in value if isinstance(item, str) and item)
    return frozenset()


def _tool_source_from_record(value: str) -> str:
    if value in {"passive", "proactive", "subagent"}:
        return value
    return "passive"


def _format_approved_tool_execution_result(result: Any) -> str:
    lines = [
        f"status: {result.status}",
        (
            "message: approved tool execution completed"
            if result.status == "success"
            else "message: approved tool execution did not complete"
        ),
        f"invoker_reached: {str(result.invoker_reached).lower()}",
        f"invoker_succeeded: {str(result.invoker_succeeded).lower()}",
    ]
    result_status = _safe_tool_result_status(result.output)
    if result_status:
        lines.append(f"tool_result_status: {result_status}")
    return "\n".join(lines)


def _safe_tool_result_status(output: object) -> str:
    parsed: object
    if isinstance(output, dict):
        parsed = output
    else:
        try:
            parsed = json.loads(str(output))
        except (TypeError, ValueError):
            return ""
    if not isinstance(parsed, dict):
        return ""
    value = parsed.get("status")
    if not isinstance(value, str):
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", value):
        return ""
    return value


def _format_approval_record(
    record: ToolApprovalRequestRecord,
    *,
    current: bool = False,
    position: int | None = None,
    total: int | None = None,
) -> str:
    lines = [
        f"id: {record.approval_request_id}",
        f"status: {record.status}",
        f"tool: {record.tool_name}",
        f"risk: {record.risk}",
        f"scope: {record.approval_scope}",
        f"args_hash: {record.args_hash}",
        f"expires_at: {record.expires_at}",
        f"policy_reason: {record.policy_reason}",
    ]
    if position is not None and total is not None:
        lines.append(f"queue_position: {position}/{total}")
    if current:
        lines.extend(["current: yes", "", _format_approval_actions(record)])
    else:
        lines.append("queue: waiting_for_previous_approval")
    return "\n".join(lines)


def _format_approval_actions(record: ToolApprovalRequestRecord) -> str:
    if record.tool_name in MANAGED_SIDE_EFFECT_TOOLS or record.risk != "write":
        approve_text = "1. 批准当前项（之后按提示 prepare/run）"
    else:
        approve_text = "1. 批准并执行当前项"
    return "\n".join(
        [
            approve_text,
            "2. 拒绝当前项",
            "3. 查看详情",
        ]
    )


def _format_approval_decision(decision: ToolApprovalDecision) -> str:
    lines = [
        f"status: {decision.action}",
        f"reason: {decision.reason}",
    ]
    if decision.approval_request_id:
        lines.append(f"id: {decision.approval_request_id}")
    if decision.tool_name:
        lines.append(f"tool: {decision.tool_name}")
    if decision.approval_scope:
        lines.append(f"scope: {decision.approval_scope}")
    if decision.args_hash:
        lines.append(f"args_hash: {decision.args_hash}")
    return "\n".join(lines)


def _format_side_effect_result(reason: str, message: str, diff_text: str = "") -> str:
    lines = [f"status: {reason}", f"message: {message}"]
    if diff_text:
        lines.extend(["", "```diff", diff_text, "```"])
    return "\n".join(lines)


def _tool_audit_query_from_command(
    content: str,
    *,
    session_key: str,
) -> ToolAuditLedgerQuery:
    parts = (content or "").strip().split()
    if len(parts) == 1:
        return ToolAuditLedgerQuery(session_key=session_key)
    if len(parts) == 2 and _int_or_none(parts[1]) is not None:
        return ToolAuditLedgerQuery(session_key=session_key, limit=int(parts[1]))

    subcommand = parts[1].lower() if len(parts) > 1 else ""
    if subcommand == "request" and len(parts) >= 3:
        return ToolAuditLedgerQuery(session_key=session_key, request_id=parts[2])
    if subcommand == "approval" and len(parts) >= 3:
        return ToolAuditLedgerQuery(
            session_key=session_key, approval_request_id=parts[2]
        )
    if subcommand == "tool" and len(parts) >= 3:
        return ToolAuditLedgerQuery(
            session_key=session_key,
            tool_name=parts[2],
            limit=_limit_arg(parts, 3),
        )
    if subcommand == "event" and len(parts) >= 3:
        return ToolAuditLedgerQuery(
            session_key=session_key,
            event_type=parts[2],
            limit=_limit_arg(parts, 3),
        )
    return ToolAuditLedgerQuery(session_key=session_key)


def _limit_arg(parts: list[str], index: int) -> int:
    if len(parts) <= index:
        return 50
    value = _int_or_none(parts[index])
    return value if value is not None else 50


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _format_tool_audit_events(events: list[ToolAuditLedgerEvent]) -> str:
    lines = ["Tool audit ledger"]
    if not events:
        lines.append("events: none")
        return "\n".join(lines)
    lines.append(f"events: {len(events)}")
    for event in events:
        lines.extend(["", _format_tool_audit_event(event)])
    return "\n".join(lines)


def _format_tool_audit_event(event: ToolAuditLedgerEvent) -> str:
    fields = [
        f"time: {_format_tool_audit_ts(event.created_at)}",
        f"event: {event.event_type}",
    ]
    if event.tool_name:
        fields.append(f"tool: {event.tool_name}")
    if event.policy_action:
        fields.append(f"policy: {event.policy_action}")
    if event.policy_reason:
        fields.append(f"reason: {event.policy_reason}")
    for label, value in (
        ("approval_status", event.approval_status),
        ("side_effect_status", event.side_effect_status),
        ("execution_status", event.execution_status),
        ("rollback_status", event.rollback_status),
    ):
        if value:
            fields.append(f"{label}: {value}")
    if event.request_id:
        fields.append(f"request: {_short_id(event.request_id)}")
    if event.approval_request_id:
        fields.append(f"approval: {_short_id(event.approval_request_id)}")
    fields.append(
        "invoker: "
        f"reached={str(event.invoker_reached).lower()} "
        f"succeeded={str(event.invoker_succeeded).lower()}"
    )
    metadata = sanitize_tool_audit_metadata(event.metadata)
    if metadata:
        items = ", ".join(f"{key}={metadata[key]}" for key in sorted(metadata))
        fields.append(f"metadata: {items}")
    return "\n".join(fields)


def _format_tool_audit_ts(value: datetime | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat() if value.tzinfo else value.isoformat()
    return value


def _short_id(value: str) -> str:
    return value if len(value) <= 12 else value[:12]


def _abort_ctx(
    state: TurnState,
    reply: str,
    *,
    approval_lifecycle: list[dict[str, object]] | None = None,
    approved_side_effect_lifecycle: list[dict[str, object]] | None = None,
) -> BeforeTurnCtx:
    extra_metadata = {}
    if approval_lifecycle:
        extra_metadata["tool_approval_lifecycle"] = approval_lifecycle
    if approved_side_effect_lifecycle:
        extra_metadata["approved_side_effect_lifecycle"] = (
            approved_side_effect_lifecycle
        )
    return BeforeTurnCtx(
        session_key=state.session_key,
        channel=state.msg.channel,
        chat_id=state.msg.chat_id,
        content=state.msg.content,
        timestamp=state.msg.timestamp,
        skill_names=[],
        retrieved_memory_block="",
        retrieval_trace_raw=None,
        history_messages=(),
        abort=True,
        abort_reply=reply,
        extra_metadata=extra_metadata,
    )


def _approval_lifecycle_from_decisions(
    store: ToolApprovalStore,
    decisions: list[ToolApprovalDecision],
    *,
    actor: str = "",
) -> list[dict[str, object]]:
    events = []
    for decision in decisions:
        if decision.action not in {"approved", "denied", "expired"}:
            continue
        record = store.get_request(decision.approval_request_id)
        if record is None:
            continue
        events.append(
            ToolApprovalRuntime.lifecycle_event_from_record(
                record,
                status=decision.action,
                actor=actor or record.decided_by,
            )
        )
    return events


def _side_effect_lifecycle_event(
    record: ApprovedSideEffectRecord,
) -> dict[str, object]:
    event: dict[str, object] = {
        "event_type": "approved_side_effect_lifecycle",
        "approval_request_id": record.approval_request_id,
        "request_id": record.request_id,
        "session_key": record.session_key,
        "actor": "status_command",
        "tool_name": record.tool_name,
        "approval_scope": record.approval_scope,
        "args_hash": record.args_hash,
        "status": record.status,
        "preview_id": record.preview_id,
        "target_path_hash": record.target_path_hash,
        "before_hash": record.before_hash,
        "after_hash": record.after_hash,
        "diff_truncated": record.diff_truncated,
        "rollback_id": record.rollback_id,
        "execution_status": record.execution_status,
        "rollback_status": record.rollback_status,
    }
    if record.tool_name == "shell":
        event.update(
            {
                "command_hash": record.command_hash,
                "sandbox_backend": record.sandbox_backend,
                "sandbox_image": record.sandbox_image,
                "network_mode": record.network_mode,
                "workspace_mount_mode": record.workspace_mount_mode,
                "timeout_seconds": record.timeout_seconds,
                "exit_code": record.exit_code,
                "stdout_hash": record.stdout_hash,
                "stderr_hash": record.stderr_hash,
                "stdout_bytes": record.stdout_bytes,
                "stderr_bytes": record.stderr_bytes,
                "stdout_truncated": record.stdout_truncated,
                "stderr_truncated": record.stderr_truncated,
                "duration_ms": record.duration_ms,
            }
        )
    return event


def _format_ts(ts: str) -> str:
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(_BEIJING_TZ)
        return f"{parsed.month}-{parsed.day} {parsed.hour:02d}:{parsed.minute:02d}"
    except ValueError:
        pass
    m = _TS_PATTERN.search(ts)
    if m:
        return f"{int(m.group(2))}-{int(m.group(3))} {m.group(4)}:{m.group(5)}"
    return ts


def _format_memory_status_reply(messages: list[dict], last_consolidated: int) -> str:
    consolidated_user = _count_real_user_messages(messages[:last_consolidated])
    total_user = _count_real_user_messages(messages)
    pending_user = max(0, total_user - consolidated_user)
    last_user_message = _latest_real_user_content(messages[:last_consolidated])

    lines = ["🧠 记忆整理状态："]
    if last_consolidated <= 0 or not last_user_message:
        lines.append("当前会话还没有完成过记忆整理。")
    elif pending_user == 0:
        lines.append("当前会话已经整理到最新的用户消息。")
    else:
        lines.append(f"上次整理到 {pending_user} 条用户消息之前。")
    if last_user_message:
        lines.extend(
            ["", "最后已整理的用户消息：", f"“{_preview_text(last_user_message)}”"]
        )
    lines.extend(
        [
            "",
            f"尚未整理的用户消息数：{pending_user}",
            f"当前会话消息数：{len(messages)}",
        ]
    )
    return "\n".join(lines)


def _count_real_user_messages(messages: list[dict]) -> int:
    return sum(1 for item in messages if _is_real_user_message(item))


def _latest_real_user_content(messages: list[dict]) -> str:
    for item in reversed(messages):
        if _is_real_user_message(item):
            return _content_to_text(item.get("content", ""))
    return ""


def _is_real_user_message(item: dict) -> bool:
    if item.get("role") != "user":
        return False
    content = _content_to_text(item.get("content", ""))
    return bool(content) and not is_context_frame(content)


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")).strip())
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def _preview_text(text: str, limit: int = 80) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "…"


def _pct_bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _pct_emoji(pct: float) -> str:
    if pct >= 80:
        return "🟢"
    if pct >= 40:
        return "🟡"
    return "🔴"
