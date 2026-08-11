from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

FIELDS = ("scene", "operation", "request_mode")
SCENES = (
    "chat",
    "memory",
    "profile",
    "task",
    "file",
    "status",
    "content",
    "action",
    "unknown",
)
OPERATIONS = (
    "answer",
    "query",
    "update",
    "plan",
    "read",
    "save",
    "execute",
    "unknown",
)
REQUEST_MODES = ("single", "compound")
VALID_SCENES = set(SCENES)
VALID_OPERATIONS = set(OPERATIONS)
VALID_REQUEST_MODES = set(REQUEST_MODES)


@dataclass(frozen=True, slots=True)
class TextPairEvalResult:
    metrics: dict[str, Any]
    errors: list[dict[str, Any]]


def route_post_processing_chat(prompt_content: str) -> str:
    prompt_content = prompt_content.replace("<think>\n\n</think>\n\n", "")
    prompt_content = prompt_content.replace("<think></think>\n\n", "")
    prompt_content = prompt_content.replace("<think>\n</think>\n\n", "")
    return prompt_content.replace("\n\n\n\n", "")


def extract_json(text: str) -> tuple[dict[str, Any] | None, bool]:
    text = text.strip()

    try:
        obj = json.loads(text)
    except Exception:
        obj = None
    if isinstance(obj, dict):
        return obj, True

    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None, False

    try:
        obj = json.loads(match.group(0))
    except Exception:
        return None, False
    if isinstance(obj, dict):
        return obj, False
    return None, False


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return sorted(normalize(item) for item in value)
    return value


def schema_valid(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False

    if set(obj) != set(FIELDS):
        return False
    if obj.get("scene") not in VALID_SCENES:
        return False
    if obj.get("operation") not in VALID_OPERATIONS:
        return False
    if obj.get("request_mode") not in VALID_REQUEST_MODES:
        return False
    return True


def _empty_metrics() -> dict[str, Any]:
    return {
        "total": 0,
        "strict_json_ok": 0,
        "json_extract_ok": 0,
        "schema_ok": 0,
        "exact_ok": 0,
        "field_ok": {field: 0 for field in FIELDS},
        "danger_confusions": {
            "chat_to_action": 0,
            "unknown_to_action": 0,
            "file_to_action": 0,
            "content_to_action": 0,
            "status_to_action": 0,
            "action_to_chat": 0,
        },
    }


def _record_danger_confusion(
    metrics: dict[str, Any],
    gold_json: dict[str, Any] | None,
    pred_json: dict[str, Any] | None,
) -> None:
    if not gold_json or not pred_json:
        return
    gold_scene = gold_json.get("scene")
    pred_scene = pred_json.get("scene")
    danger_confusions = metrics["danger_confusions"]

    if gold_scene == "chat" and pred_scene == "action":
        danger_confusions["chat_to_action"] += 1
    if gold_scene == "unknown" and pred_scene == "action":
        danger_confusions["unknown_to_action"] += 1
    if gold_scene == "file" and pred_scene == "action":
        danger_confusions["file_to_action"] += 1
    if gold_scene == "content" and pred_scene == "action":
        danger_confusions["content_to_action"] += 1
    if gold_scene == "status" and pred_scene == "action":
        danger_confusions["status_to_action"] += 1
    if gold_scene == "action" and pred_scene == "chat":
        danger_confusions["action_to_chat"] += 1


def evaluate_text_pairs(
    pairs: Iterable[tuple[str, str]],
    *,
    inputs: Sequence[Any] | None = None,
) -> TextPairEvalResult:
    metrics = _empty_metrics()
    errors: list[dict[str, Any]] = []

    for index, (gold_text, pred_text) in enumerate(pairs, start=1):
        gold_json, _ = extract_json(gold_text)
        pred_json, pred_strict = extract_json(pred_text)
        metrics["total"] += 1

        if pred_strict:
            metrics["strict_json_ok"] += 1
        if pred_json is not None:
            metrics["json_extract_ok"] += 1
        if schema_valid(pred_json):
            metrics["schema_ok"] += 1

        is_exact = False
        if pred_json is not None and gold_json is not None:
            if normalize(pred_json) == normalize(gold_json):
                metrics["exact_ok"] += 1
                is_exact = True
            for field in FIELDS:
                if normalize(pred_json.get(field)) == normalize(gold_json.get(field)):
                    metrics["field_ok"][field] += 1

        _record_danger_confusion(metrics, gold_json, pred_json)

        if not is_exact:
            errors.append(
                {
                    "line": index,
                    "input": inputs[index - 1] if inputs is not None else None,
                    "gold": gold_text,
                    "pred": pred_text,
                    "pred_json": pred_json,
                    "schema_valid": schema_valid(pred_json),
                }
            )

    return TextPairEvalResult(metrics=metrics, errors=errors)


def _pct(value: int, total: int) -> str:
    if total <= 0:
        return "0.00%"
    return f"{value / total:.2%}"


def _load_model(args: argparse.Namespace) -> tuple[Any, Any, Any]:
    import torch
    from argparse import Namespace
    from eval_llm import init_model

    model_args = Namespace(
        load_from=args.load_from,
        save_dir=args.save_dir,
        weight=args.weight,
        lora_weight=args.lora_weight,
        hidden_size=args.hidden_size,
        num_hidden_layers=args.num_hidden_layers,
        use_moe=args.use_moe,
        inference_rope_scaling=False,
        device=args.device,
    )
    model, tokenizer = init_model(model_args)
    return model, tokenizer, torch


def _predict_one(
    model: Any,
    tokenizer: Any,
    torch_module: Any,
    prompt_conv: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    prompt = tokenizer.apply_chat_template(
        prompt_conv,
        tokenize=False,
        add_generation_prompt=True,
        open_thinking=False,
    )
    prompt = route_post_processing_chat(prompt)

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
    ).to(args.device)

    with torch_module.no_grad():
        generated_ids = model.generate(
            inputs=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=1,
        )

    return tokenizer.decode(
        generated_ids[0][len(inputs["input_ids"][0]) :],
        skip_special_tokens=True,
    ).strip()


def _read_eval_rows(data_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with data_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            conversations = row["conversations"]
            if not isinstance(conversations, list) or len(conversations) < 2:
                raise ValueError(f"{data_path}:{line_no}: invalid conversations")
            rows.append(row)
    return rows


def _print_report(args: argparse.Namespace, metrics: dict[str, Any]) -> None:
    total = metrics["total"]
    print("\n===== Route V4 Eval Result =====")
    print(f"数据集: {args.data_path}")
    print(f"模型: {args.weight} + {args.lora_weight}")
    print(f"总数: {total}")
    print(
        f"严格只输出 JSON: {metrics['strict_json_ok']}/{total} = "
        f"{_pct(metrics['strict_json_ok'], total)}"
    )
    print(
        f"可提取 JSON: {metrics['json_extract_ok']}/{total} = "
        f"{_pct(metrics['json_extract_ok'], total)}"
    )
    print(
        f"Schema 合法: {metrics['schema_ok']}/{total} = "
        f"{_pct(metrics['schema_ok'], total)}"
    )
    print(
        f"完全匹配: {metrics['exact_ok']}/{total} = "
        f"{_pct(metrics['exact_ok'], total)}"
    )

    print("\n字段准确率:")
    for field in FIELDS:
        value = metrics["field_ok"][field]
        print(f"{field}: {value}/{total} = {_pct(value, total)}")

    print("\n危险混淆:")
    for name, value in metrics["danger_confusions"].items():
        print(f"{name}: {value}")

    print(f"\n错误样本已保存到: {args.errors_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate MiniRoute V4 scene routing.")
    parser.add_argument("--data_path", default="dataset/route_v4_valid.jsonl")
    parser.add_argument("--weight", default="full_sft")
    parser.add_argument("--lora_weight", default="lora_route_v4_scene")
    parser.add_argument("--save_dir", default="out")
    parser.add_argument("--load_from", default="model")
    parser.add_argument("--hidden_size", type=int, default=768)
    parser.add_argument("--num_hidden_layers", type=int, default=8)
    parser.add_argument("--use_moe", type=int, default=0)
    parser.add_argument("--max_new_tokens", type=int, default=60)
    parser.add_argument("--limit", type=int, default=0, help="0 表示测试全部")
    parser.add_argument("--errors_path", default="result/route_v4_eval_errors.jsonl")
    parser.add_argument("--device", default=None)
    args = parser.parse_args(argv)

    if args.device is None:
        import torch

        args.device = "cuda" if torch.cuda.is_available() else "cpu"

    rows = _read_eval_rows(Path(args.data_path))
    if args.limit:
        rows = rows[: args.limit]

    model, tokenizer, torch_module = _load_model(args)
    gold_and_pred: list[tuple[str, str]] = []
    prompt_inputs: list[Any] = []

    for index, row in enumerate(rows, start=1):
        conversations = row["conversations"]
        prompt_conv = conversations[:-1]
        gold_text = str(conversations[-1]["content"]).strip()
        pred_text = _predict_one(model, tokenizer, torch_module, prompt_conv, args)
        gold_and_pred.append((gold_text, pred_text))
        prompt_inputs.append(prompt_conv)

        if index % 50 == 0:
            print(f"已测试 {index} 条...")

    result = evaluate_text_pairs(gold_and_pred, inputs=prompt_inputs)

    errors_path = Path(args.errors_path)
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    with errors_path.open("w", encoding="utf-8") as handle:
        for err in result.errors:
            handle.write(json.dumps(err, ensure_ascii=False) + "\n")

    _print_report(args, result.metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
