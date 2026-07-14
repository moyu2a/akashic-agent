from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

TurnCompletionAction = Literal["continue_react", "final_only"]


@dataclass(frozen=True)
class TurnCompletionDecision:
    action: TurnCompletionAction
    reason: str
    model_hint: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)
