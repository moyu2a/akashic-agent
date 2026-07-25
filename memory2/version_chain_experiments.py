from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VersionChainShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_version_chain_shadow_result(
    *,
    memory_items: list[dict[str, object]],
    replacements: list[dict[str, object]],
    recalled_items: list[dict[str, object]],
) -> VersionChainShadowResult:
    items_by_id = _items_by_id(memory_items, replacements, recalled_items)
    children = _children_by_old_item(replacements)
    parents = _parents_by_new_item(replacements)
    replacement_ids = _replacement_item_ids(replacements)
    roots = _root_ids(replacement_ids, parents)
    chains = [_walk_chain(root, children) for root in roots]
    active_leaf_ids = _active_leaf_ids(chains, children, items_by_id)
    recalled_ids = _ids(recalled_items)
    stale_recalled_ids = [
        item_id
        for item_id in recalled_ids
        if _status(items_by_id.get(item_id)) != "active"
        or (item_id in replacement_ids and item_id not in active_leaf_ids)
    ]
    rollback_candidates = [
        _clean_id(rep.get("old_item_id"))
        for rep in replacements
        if _clean_id(rep.get("old_item_id"))
        and _clean_id(rep.get("new_item_id")) in active_leaf_ids
    ]
    conflict_chains = [
        chain
        for chain in chains
        if len([item_id for item_id in chain if item_id in active_leaf_ids]) > 1
    ]

    return VersionChainShadowResult(
        baseline_result={
            "baseline_recalled_ids": recalled_ids,
            "baseline_recalled_count": len(recalled_ids),
        },
        experimental_result={
            "chain_count": len(chains),
            "chains": chains,
            "active_leaf_ids": active_leaf_ids,
            "stale_recalled_ids": stale_recalled_ids,
            "rollback_candidate_ids": sorted(set(rollback_candidates)),
        },
        metrics={
            "replacement_count": len(replacements),
            "chain_count": len(chains),
            "avg_chain_depth": _avg([len(chain) for chain in chains]),
            "max_chain_depth": max([len(chain) for chain in chains], default=0),
            "active_leaf_count": len(active_leaf_ids),
            "stale_recalled_count": len(stale_recalled_ids),
            "superseded_recalled_count": sum(
                1
                for item_id in recalled_ids
                if _status(items_by_id.get(item_id)) == "superseded"
            ),
            "rollback_candidate_count": len(set(rollback_candidates)),
            "conflict_chain_count": len(conflict_chains),
            "orphan_replacement_count": _orphan_replacement_count(
                replacements,
                items_by_id,
            ),
        },
    )


def _items_by_id(
    memory_items: list[dict[str, object]],
    replacements: list[dict[str, object]],
    recalled_items: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    items: dict[str, dict[str, object]] = {}
    for item in memory_items:
        item_id = _clean_id(item.get("id"))
        if item_id:
            items[item_id] = dict(item)
    for replacement in replacements:
        old_id = _clean_id(replacement.get("old_item_id"))
        if old_id:
            items.setdefault(
                old_id,
                {
                    "id": old_id,
                    "memory_type": replacement.get("old_memory_type", ""),
                    "summary": replacement.get("old_summary", ""),
                    "source_ref": replacement.get("old_source_ref", ""),
                    "happened_at": replacement.get("old_happened_at", ""),
                    "extra_json": replacement.get("old_extra_json", {}),
                    "status": "superseded",
                },
            )
        new_id = _clean_id(replacement.get("new_item_id"))
        if new_id:
            items.setdefault(
                new_id,
                {
                    "id": new_id,
                    "memory_type": replacement.get("new_memory_type", ""),
                    "summary": replacement.get("new_summary", ""),
                    "source_ref": replacement.get("new_source_ref", ""),
                    "happened_at": replacement.get("new_happened_at", ""),
                    "extra_json": replacement.get("new_extra_json", {}),
                    "status": "active",
                },
            )
    for item in recalled_items:
        item_id = _clean_id(item.get("id"))
        if not item_id:
            continue
        merged = dict(items.get(item_id, {}))
        merged.update(item)
        merged["id"] = item_id
        items[item_id] = merged
    return items


def _replacement_item_ids(replacements: list[dict[str, object]]) -> set[str]:
    ids: set[str] = set()
    for replacement in replacements:
        old_id = _clean_id(replacement.get("old_item_id"))
        new_id = _clean_id(replacement.get("new_item_id"))
        if old_id:
            ids.add(old_id)
        if new_id:
            ids.add(new_id)
    return ids


def _children_by_old_item(
    replacements: list[dict[str, object]],
) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for replacement in replacements:
        old_id = _clean_id(replacement.get("old_item_id"))
        new_id = _clean_id(replacement.get("new_item_id"))
        if not old_id or not new_id:
            continue
        children.setdefault(old_id, [])
        if new_id not in children[old_id]:
            children[old_id].append(new_id)
    return {key: sorted(value) for key, value in children.items()}


def _parents_by_new_item(replacements: list[dict[str, object]]) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = {}
    for replacement in replacements:
        old_id = _clean_id(replacement.get("old_item_id"))
        new_id = _clean_id(replacement.get("new_item_id"))
        if not old_id or not new_id:
            continue
        parents.setdefault(new_id, [])
        if old_id not in parents[new_id]:
            parents[new_id].append(old_id)
    return {key: sorted(value) for key, value in parents.items()}


def _root_ids(replacement_ids: set[str], parents: dict[str, list[str]]) -> list[str]:
    return sorted(item_id for item_id in replacement_ids if item_id not in parents)


def _walk_chain(
    root: str,
    children: dict[str, list[str]],
    seen: set[str] | None = None,
) -> list[str]:
    visited = seen if seen is not None else set()
    if root in visited:
        return []
    visited.add(root)
    chain = [root]
    for child_id in children.get(root, []):
        chain.extend(_walk_chain(child_id, children, visited))
    return chain


def _active_leaf_ids(
    chains: list[list[str]],
    children: dict[str, list[str]],
    items_by_id: dict[str, dict[str, object]],
) -> list[str]:
    active: list[str] = []
    for chain in chains:
        for item_id in chain:
            if children.get(item_id):
                continue
            if _status(items_by_id.get(item_id)) != "active":
                continue
            if item_id not in active:
                active.append(item_id)
    return active


def _ids(items: list[dict[str, object]]) -> list[str]:
    result: list[str] = []
    for item in items:
        item_id = _clean_id(item.get("id"))
        if item_id:
            result.append(item_id)
    return result


def _status(item: dict[str, object] | None) -> str:
    if item is None:
        return ""
    return str(item.get("status") or "active").strip() or "active"


def _orphan_replacement_count(
    replacements: list[dict[str, object]],
    items_by_id: dict[str, dict[str, object]],
) -> int:
    count = 0
    for replacement in replacements:
        old_id = _clean_id(replacement.get("old_item_id"))
        new_id = _clean_id(replacement.get("new_item_id"))
        if not old_id or not new_id:
            count += 1
            continue
        if old_id not in items_by_id or new_id not in items_by_id:
            count += 1
    return count


def _avg(values: list[int]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _clean_id(value: object) -> str:
    return str(value or "").strip()
