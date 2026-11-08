"""DeepSeek chat integration for the assistant tool layer.

DeepSeek is OpenAI-compatible; the OpenAI SDK is pointed at
``https://api.deepseek.com/v1``. The API key comes from ``DEEPSEEK_API_KEY``
and the model is ``deepseek-chat``. Real mode is the default and requires that
key. ``ASSISTANT_FAKE_LLM=true`` enables a canned mode for exercising the tool
pipeline without a key.

Read tools execute immediately. Write tools never execute in this phase; they
return a pending action for the caller to present for confirmation.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from .tools import ToolResult, get_tool, list_tools


class AssistantUnavailable(Exception):
    """The assistant cannot service a request with its current configuration."""


ASSISTANT_FAKE_LLM_ENV_VAR = "ASSISTANT_FAKE_LLM"
MODEL = "deepseek-chat"


def is_fake_llm_mode() -> bool:
    """Return whether the assistant's canned test mode is enabled."""
    return os.environ.get(ASSISTANT_FAKE_LLM_ENV_VAR, "").strip().lower() == "true"


def _get_client():
    """Create an OpenAI-compatible DeepSeek client, unless fake mode is active."""
    if is_fake_llm_mode():
        return None
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise AssistantUnavailable("DEEPSEEK_API_KEY is not set")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AssistantUnavailable(
            "The openai package is required for DeepSeek integration"
        ) from exc
    return OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")


def _tools_to_openai_schema() -> list[dict[str, Any]]:
    """Convert registered tools to the OpenAI function-calling schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.input_schema,
            },
        }
        for spec in list_tools()
    ]


def _tool_summary(tool_name: str, result: ToolResult) -> str:
    """Make a brief reply from the actual data returned by a read tool."""
    if not result.ok:
        return f"{tool_name} failed: {result.error or 'unknown error'}"
    data = result.data
    if isinstance(data, dict) and data.get("status"):
        return f"{tool_name.replace('_', ' ')}: {data['status']} — {data.get('reason', '')}".strip()
    if tool_name in {"get_broker_balance", "get_paper_balance"} and isinstance(data, dict):
        if "balance" in data and "currency" in data:
            label = "MT5 Demo" if tool_name == "get_broker_balance" else "Paper"
            return f"{label} balance: {float(data['balance']):,.2f} {data['currency']}."
    if tool_name == "get_latest_signal" and isinstance(data, dict):
        return (
            f"Latest {data.get('asset', 'market')} signal: {data.get('signal')} — "
            f"{data.get('reason')}; price {data.get('price')}."
        )
    if tool_name == "get_research_status" and isinstance(data, dict):
        instruments = data.get("instruments", [])
        labels = [str(item.get("instrument_id", item.get("asset", "instrument")))
                  for item in instruments if isinstance(item, dict)]
        suffix = f" Registered instruments: {', '.join(labels)}." if labels else ""
        return f"Research status has {data.get('count', len(instruments))} instruments.{suffix}"
    return f"{tool_name.replace('_', ' ')} returned: {json.dumps(data, default=str)}"


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            return content if isinstance(content, str) else str(content)
    return ""


def _fake_turn(messages: list[dict]) -> dict:
    """Run one canned tool call selected from the latest user message."""
    text = _last_user_text(messages)
    lowered = text.lower()

    if "balance" in lowered and "mt5" in lowered:
        tool_name, args = "get_broker_balance", {"broker": "mt5_demo"}
    elif "balance" in lowered and "paper" in lowered:
        tool_name, args = "get_paper_balance", {}
    elif "signal" in lowered:
        tool_name, args = "get_latest_signal", {"instrument": "BTC/USDT"}
    elif "research" in lowered or "instruments" in lowered:
        tool_name, args = "get_research_status", {}
    elif "set target" in lowered or "daily target" in lowered:
        tool_name, args = "set_daily_target", {"target_amount": 100.0}
    else:
        return {
            "reply": (
                "In fake LLM mode, no matching keyword. Try 'mt5 balance', "
                "'paper balance', 'signal', 'research', or 'set daily target to 100'."
            ),
            "pending_action": None,
        }

    registered = get_tool(tool_name)
    if registered is None:
        raise AssistantUnavailable(f"tool {tool_name!r} is not registered")
    spec, fn = registered
    try:
        result = fn(**args)
    except Exception as exc:
        raise AssistantUnavailable(f"tool {tool_name} failed: {exc}") from exc

    if spec.category == "read":
        return {"reply": _tool_summary(tool_name, result), "pending_action": None}

    if not result.ok:
        return {
            "reply": f"I could not propose that action: {result.error or 'refused'}",
            "pending_action": None,
        }

    pending_action = dict(result.data or {})
    pending_action.update(
        {
            "confirmation_id": result.confirmation_id,
            "tool_name": tool_name,
            "args": args,
            "description": spec.description,
        }
    )
    return {
        "reply": "I would like to set Daily Target to $100.00. Confirm to proceed.",
        "pending_action": pending_action,
    }


def _write_reply(tool_name: str, args: dict, description: str) -> str:
    if tool_name == "set_daily_target":
        action = f"set Daily Target to ${float(args['target_amount']):,.2f}"
    elif tool_name == "set_high_risk_fraction":
        action = f"set High-Risk sizing to {float(args['risk_fraction']):.1%}"
    elif tool_name == "cancel_manual_action":
        action = "cancel the pending manual paper action"
    elif tool_name == "place_broker_order":
        action = (
            f"place a {args['side']} {args['order_type']} order for "
            f"{args['quantity']} {args['instrument']} on {args['broker']}"
        )
    elif tool_name == "cancel_broker_order":
        action = f"cancel order {args['client_order_id']} on {args['broker']}"
    elif tool_name == "close_broker_position":
        action = f"close the {args['instrument']} position on {args['broker']}"
    else:
        action = description.rstrip(".")
    return f"I would like to {action}. Confirm to proceed."


def _pending_write(tool_name: str, args: dict) -> dict:
    registered = get_tool(tool_name)
    if registered is None:
        raise AssistantUnavailable(f"tool {tool_name!r} is not registered")
    spec, fn = registered
    try:
        # Phase A write functions only validate and propose; they never perform
        # the described action. Running them here applies their gates before a
        # confirmation is offered.
        result = fn(**args)
    except Exception as exc:
        raise AssistantUnavailable(f"tool {tool_name} failed: {exc}") from exc
    if not result.ok:
        return {
            "reply": f"I could not propose that action: {result.error or 'refused'}",
            "pending_action": None,
        }
    pending_action = dict(result.data or {})
    pending_action.update(
        {
            "confirmation_id": result.confirmation_id,
            "tool_name": tool_name,
            "args": args,
            "description": spec.description,
        }
    )
    return {
        "reply": _write_reply(tool_name, args, spec.description),
        "pending_action": pending_action,
    }


def run_assistant_turn(messages: list[dict], max_tool_rounds: int = 5) -> dict:
    """Run one assistant turn, executing reads and returning writes as proposals."""
    if is_fake_llm_mode():
        return _fake_turn(messages)

    client = _get_client()
    conversation = list(messages)
    schemas = _tools_to_openai_schema()

    for _round in range(max_tool_rounds):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=conversation,
                tools=schemas,
                tool_choice="auto",
            )
        except Exception as exc:
            raise AssistantUnavailable(f"DeepSeek request failed: {exc}") from exc

        message = response.choices[0].message
        calls = message.tool_calls or []
        if not calls:
            return {"reply": message.content or "", "pending_action": None}

        assistant_calls = []
        read_calls = []
        for call in calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except (TypeError, json.JSONDecodeError) as exc:
                raise AssistantUnavailable(
                    f"DeepSeek returned invalid arguments for {name}: {exc}"
                ) from exc
            if not isinstance(args, dict):
                raise AssistantUnavailable(
                    f"DeepSeek returned non-object arguments for {name}"
                )
            registered = get_tool(name)
            if registered is None:
                read_calls.append((call.id, name, args, None))
                assistant_calls.append(call)
                continue
            spec, _fn = registered
            if spec.category != "read":
                return _pending_write(name, args)
            assistant_calls.append(call)
            read_calls.append((call.id, name, args, registered))

        conversation.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in assistant_calls
                ],
            }
        )

        for call_id, name, args, registered in read_calls:
            if registered is None:
                tool_payload = {"ok": False, "error": f"unknown tool: {name}"}
            else:
                _spec, fn = registered
                try:
                    result = fn(**args)
                    tool_payload = asdict(result)
                except Exception as exc:
                    tool_payload = {"ok": False, "error": str(exc)}
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(tool_payload, default=str),
                }
            )

    raise AssistantUnavailable("assistant exceeded max_tool_rounds")


SYSTEM_PROMPT = (
    "You are the Crypto Paper Lab assistant. You help the user inspect their "
    "paper trading engine, live broker accounts, research status, and market "
    "data. You have tools to READ state and to PROPOSE WRITE ACTIONS. You "
    "must NEVER claim to have executed a write action — write actions require "
    "the user to confirm them in the UI before they run. When you propose a "
    "write action, explain what it will do briefly, then wait for confirmation. "
    "If a tool returns an error, report the exact error to the user. Never "
    "invent numbers, balances, positions, or signals — always use tool calls. "
    "Keep replies short and specific."
)


def build_initial_messages(
    user_message: str, history: list[dict] | None = None
) -> list[dict]:
    """Build the system, prior history, and latest user message sequence."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages
