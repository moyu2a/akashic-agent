from __future__ import annotations

from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.tool_access_types import ToolAccessContext, ToolAccessPlan

_SHELL_TOOL_NAMES = frozenset({"shell"})


class TaskExecutionAccessPolicy:
    name = "TaskExecutionAccessPolicy"

    def build_plan(self, context: ToolAccessContext) -> ToolAccessPlan:
        contract = context.turn_metadata.get("task_execution_contract")
        if not isinstance(contract, TaskExecutionTurnContract) or not contract.active:
            return ToolAccessPlan()

        universe = _registered_universe(context)
        providers = _providers_by_capability(context, universe)
        missing_required = sorted(
            capability
            for capability in contract.required_capabilities
            if not providers.get(capability)
        )
        resolved_capabilities = {
            capability: sorted(providers.get(capability, frozenset()))
            for capability in sorted(contract.allowed_capabilities)
        }
        trace_metadata = {
            **contract.to_trace_metadata(),
            "resolved_capabilities": resolved_capabilities,
            "missing_required_capabilities": missing_required,
        }
        if missing_required:
            missing_text = ", ".join(missing_required)
            return ToolAccessPlan(
                visible_suppress=universe,
                tool_search_block=universe,
                execution_block=universe,
                reason="task_execution_required_capability_missing",
                matched_terms=contract.matched_terms,
                policies=(self.name,),
                filter_error=True,
                policy_metadata={"task_execution": trace_metadata},
                task_execution_contract=contract,
                strict_capability_scope=True,
                final_only=contract.phase in {"waiting_authorization", "terminal"},
                model_hints=(
                    f"Task execution action {contract.action} is unavailable because "
                    f"required capability {missing_text} has no enabled registered "
                    "provider. Do not use unrelated tools as a fallback.",
                ),
            )

        allowed_tools = frozenset(
            tool_name
            for capability in contract.allowed_capabilities
            for tool_name in providers.get(capability, frozenset())
        )
        dynamic_tools = frozenset()
        if contract.phase == "work":
            allowed_tools = allowed_tools | _registered_tools_named(
                context, universe, "tool_search"
            )
            dynamic_tools = frozenset(
                tool_name
                for tool_name in universe
                if tool_name not in context.disabled_tools
                and tool_name not in _SHELL_TOOL_NAMES
                and context.tool_risks.get(tool_name) == "read-only"
                and not (
                    context.tool_capabilities.get(tool_name, frozenset())
                    & {
                        "task_execution.begin",
                        "task_execution.inspect",
                        "task_execution.finish",
                        "task_execution.defer",
                        "task_execution.abort",
                    }
                )
                and tool_name not in allowed_tools
            )

        blocked_tools = universe - allowed_tools - dynamic_tools
        return ToolAccessPlan(
            visible_add=allowed_tools,
            visible_suppress=blocked_tools,
            tool_search_block=blocked_tools,
            execution_block=blocked_tools,
            reason=contract.reason,
            matched_terms=contract.matched_terms,
            policies=(self.name,),
            policy_metadata={"task_execution": trace_metadata},
            task_execution_contract=contract,
            strict_capability_scope=True,
            execution_dynamic_tools=dynamic_tools,
            final_only=contract.phase in {"waiting_authorization", "terminal"},
        )

    def observe_tool_result(
        self,
        plan: ToolAccessPlan,
        tool_name: str,
        result_text: str,
        *,
        execution_status: str = "success",
    ) -> ToolAccessPlan:
        return plan


def _registered_universe(context: ToolAccessContext) -> frozenset[str]:
    if context.registered_tools:
        return context.registered_tools
    return frozenset(
        set(context.tool_capabilities)
        | set(context.tool_risks)
        | set(context.always_on_tools)
        | set(context.lru_preloaded_tools)
    )


def _providers_by_capability(
    context: ToolAccessContext,
    universe: frozenset[str],
) -> dict[str, frozenset[str]]:
    providers: dict[str, set[str]] = {}
    for tool_name, capabilities in context.tool_capabilities.items():
        if tool_name not in universe or tool_name in context.disabled_tools:
            continue
        for capability in capabilities:
            providers.setdefault(capability, set()).add(tool_name)
    return {
        capability: frozenset(tool_names)
        for capability, tool_names in providers.items()
    }


def _registered_tools_named(
    context: ToolAccessContext,
    universe: frozenset[str],
    tool_name: str,
) -> frozenset[str]:
    if tool_name in universe and tool_name not in context.disabled_tools:
        return frozenset({tool_name})
    return frozenset()
