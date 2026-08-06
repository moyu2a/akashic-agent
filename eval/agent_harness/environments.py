from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol


class EvalEnvironment(Protocol):
    def reset(self, seed: int) -> None: ...

    def snapshot(self) -> object: ...

    def restore(self, snapshot: object) -> None: ...

    def inspect_state(self) -> dict[str, object]: ...

    def cleanup(self) -> None: ...


class DeterministicFakeEnvironment:
    def __init__(
        self,
        *,
        initial_state: dict[str, object] | None = None,
        tool_results: dict[str, object] | None = None,
    ) -> None:
        self._initial_state = deepcopy(initial_state or {})
        self._state = deepcopy(self._initial_state)
        self._tool_results = deepcopy(tool_results or {})
        self.seed: int | None = None

    def reset(self, seed: int) -> None:
        self.seed = seed
        self._state = deepcopy(self._initial_state)

    def snapshot(self) -> dict[str, object]:
        return deepcopy(self._state)

    def restore(self, snapshot: object) -> None:
        if not isinstance(snapshot, dict):
            raise TypeError("fake environment snapshot must be a dict")
        self._state = deepcopy(snapshot)

    def inspect_state(self) -> dict[str, object]:
        return deepcopy(self._state)

    def mutate(self, values: dict[str, object]) -> None:
        self._state.update(deepcopy(values))

    def tool_result(self, tool_name: str) -> object:
        return deepcopy(self._tool_results.get(tool_name))

    def cleanup(self) -> None:
        self._state = deepcopy(self._initial_state)
