# MiniRoute V1 Error Analysis

## Status

No model error analysis has been performed yet because MiniMind training has not
run in this repository environment.

After the first trained model is evaluated, errors should be grouped into:

- `invalid_json`
- `intent_mismatch`
- `memory_false_negative`
- `memory_false_positive`
- `tool_false_negative`
- `tool_false_positive`
- `scope_overopen`
- `risk_underestimate`
- `risk_overestimate`

## First Analysis Priority

The first analysis pass should focus on:

- high-risk requests predicted below `high_risk`;
- requests that incorrectly open `shell_tools`;
- memory queries predicted as `chat`;
- ability questions predicted as execution requests;
- JSON outputs that cannot be parsed.
