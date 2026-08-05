"""api-cost-estimate: estimate chat-completion API cost BEFORE actually
calling any model. Pure local estimation -- no network calls, no API key
needed. Not tied to any specific project, dataset, or domain: question
text can come from any file (plain text, one question per line, or a
JSON array of strings / objects with a text-like field), or you can skip
the file entirely and just specify a question count + average length.

Accounts for:
- multiple models being compared (each with its own input/output pricing)
- an optional judge model (LLM-as-a-Judge), added on top of the compared models
- number of calls per question (reruns, e.g. to average out variance)
- "thinking depth" / reasoning effort, which inflates output-token usage
  for reasoning models (rough multiplier, not exact -- provider-specific)

Usage:
    python estimate_cost.py \
        --model "gpt-x:2.50:10.00" \
        --model "claude-x:3.00:15.00:medium" \
        --judge "judge-model:2.50:10.00" \
        --questions-file path/to/questions.json \
        --reruns 1

    (or, without a file:)
    python estimate_cost.py --model "..." --num-questions 10 --avg-question-chars 200

--model / --judge format: "name:price_in_per_1M_usd:price_out_per_1M_usd[:effort]"
  effort (optional) is one of: low, medium, high, xhigh -- applies a rough
  output-token multiplier to approximate reasoning-token overhead.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Rough chars-per-token approximation for mixed CJK/English text.
# This is NOT an exact tokenizer count -- flagged explicitly in the output.
CHARS_PER_TOKEN_ESTIMATE = 2.0

# Rough, illustrative reasoning-effort output-token multipliers.
# Actual behavior is provider/model-specific; override with real numbers
# via --avg-answer-tokens if you know them.
EFFORT_MULTIPLIERS = {"low": 1.0, "medium": 2.0, "high": 4.0, "xhigh": 8.0}

TEXT_KEYS = ("question", "text", "prompt", "content")


@dataclass
class Participant:
    name: str
    price_in_per_1m: float
    price_out_per_1m: float
    effort: str | None = None

    @property
    def output_multiplier(self) -> float:
        return EFFORT_MULTIPLIERS.get(self.effort, 1.0) if self.effort else 1.0

    @classmethod
    def parse(cls, spec: str) -> "Participant":
        parts = spec.split(":")
        if len(parts) not in (3, 4):
            raise ValueError(
                f"Invalid --model/--judge spec '{spec}'. "
                "Expected 'name:price_in_per_1M:price_out_per_1M[:effort]'."
            )
        name, price_in, price_out = parts[0], float(parts[1]), float(parts[2])
        effort = parts[3] if len(parts) == 4 else None
        if effort and effort not in EFFORT_MULTIPLIERS:
            valid = ", ".join(EFFORT_MULTIPLIERS)
            raise ValueError(f"Unknown effort '{effort}' in '{spec}'. Valid: {valid}")
        return cls(name, price_in, price_out, effort)


def load_question_texts(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("questions", [])
        texts = []
        for item in items:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                for key in TEXT_KEYS:
                    if key in item and isinstance(item[key], str):
                        texts.append(item[key])
                        break
        return texts

    # plain text: one question per line, skip blanks
    return [line.strip() for line in raw.splitlines() if line.strip()]


def estimate_tokens(char_count: int) -> float:
    return char_count / CHARS_PER_TOKEN_ESTIMATE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", action="append", default=[], help="A model being compared: 'name:price_in:price_out[:effort]' (repeatable)")
    parser.add_argument("--judge", default=None, help="Optional judge model: 'name:price_in:price_out[:effort]'")
    parser.add_argument("--questions-file", type=Path, default=None, help="File with question texts (.json array/objects, or plain text one-per-line)")
    parser.add_argument("--num-questions", type=int, default=None, help="Question count, used if --questions-file is omitted")
    parser.add_argument("--avg-question-chars", type=int, default=200, help="Avg chars per question, used if --questions-file is omitted (default: 200)")
    parser.add_argument("--context-overhead-tokens", type=int, default=500, help="Extra input tokens per call for system prompt / retrieved context (default: 500)")
    parser.add_argument("--avg-answer-tokens", type=int, default=300, help="Avg output tokens per model answer, before any effort multiplier (default: 300)")
    parser.add_argument("--avg-judge-tokens", type=int, default=150, help="Avg output tokens per judge verdict (default: 150)")
    parser.add_argument("--reruns", type=int, default=1, help="How many times each question is sent per model, e.g. to average out variance (default: 1)")
    args = parser.parse_args()

    if not args.model:
        print("[api-cost-estimate] Need at least one --model.")
        return 1

    models = [Participant.parse(spec) for spec in args.model]
    judge = Participant.parse(args.judge) if args.judge else None

    if args.questions_file:
        if not args.questions_file.exists():
            print(f"[api-cost-estimate] File not found: {args.questions_file}")
            return 1
        texts = load_question_texts(args.questions_file)
        if not texts:
            print(f"[api-cost-estimate] No question text found in {args.questions_file}")
            return 1
        num_questions = len(texts)
        avg_question_tokens = sum(estimate_tokens(len(t)) for t in texts) / num_questions
        source = f"{args.questions_file} ({num_questions} questions, real text)"
    else:
        num_questions = args.num_questions
        if not num_questions:
            print("[api-cost-estimate] Need --questions-file or --num-questions.")
            return 1
        avg_question_tokens = estimate_tokens(args.avg_question_chars)
        source = f"manual input ({num_questions} questions, assumed {args.avg_question_chars} chars each)"

    input_tokens_per_call = avg_question_tokens + args.context_overhead_tokens
    total_calls = num_questions * args.reruns

    print(f"[api-cost-estimate] Question source: {source}")
    print(f"[api-cost-estimate] Reruns per question: {args.reruns} -> {total_calls} calls per model")
    print(f"[api-cost-estimate] Est. input tokens/call: {input_tokens_per_call:,.0f} (question ~{avg_question_tokens:,.0f} + context overhead {args.context_overhead_tokens:,})\n")

    grand_total_usd = 0.0
    all_answer_tokens_per_question = 0.0

    for m in models:
        output_tokens_per_call = args.avg_answer_tokens * m.output_multiplier
        in_cost = total_calls * input_tokens_per_call / 1_000_000 * m.price_in_per_1m
        out_cost = total_calls * output_tokens_per_call / 1_000_000 * m.price_out_per_1m
        cost = in_cost + out_cost
        grand_total_usd += cost
        all_answer_tokens_per_question += output_tokens_per_call
        effort_note = f", effort={m.effort} (x{m.output_multiplier})" if m.effort else ""
        print(f"[api-cost-estimate] Model '{m.name}'{effort_note}: {total_calls} calls, "
              f"~{output_tokens_per_call:,.0f} output tokens/call -> US${cost:.4f}")

    if judge:
        # Judge sees: the question + every compared model's answer + instructions.
        judge_input_tokens = input_tokens_per_call + all_answer_tokens_per_question + 200
        judge_output_tokens = args.avg_judge_tokens * judge.output_multiplier
        judge_calls = num_questions  # judge runs once per question, not per rerun x model
        in_cost = judge_calls * judge_input_tokens / 1_000_000 * judge.price_in_per_1m
        out_cost = judge_calls * judge_output_tokens / 1_000_000 * judge.price_out_per_1m
        cost = in_cost + out_cost
        grand_total_usd += cost
        effort_note = f", effort={judge.effort} (x{judge.output_multiplier})" if judge.effort else ""
        print(f"[api-cost-estimate] Judge '{judge.name}'{effort_note}: {judge_calls} calls, "
              f"~{judge_input_tokens:,.0f} input / ~{judge_output_tokens:,.0f} output tokens/call -> US${cost:.4f}")

    print(f"\n[api-cost-estimate] ESTIMATED TOTAL: US${grand_total_usd:.4f}")
    print(
        "\n[api-cost-estimate] This is an approximation, not an exact tokenizer count "
        "(chars/token ratio and effort multipliers are rough heuristics -- override "
        "--avg-answer-tokens/--avg-judge-tokens with real numbers if you have them). "
        "If a real run's actual usage differs noticeably, treat that as new calibration "
        "data for next time, not a bug in this estimate."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
