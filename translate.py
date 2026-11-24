import time
import uuid

from config import DEFAULT_MAX_TOKENS

STOP_REASONS = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
}


def _flatten(content) -> str:
    """OpenAI content may be a string or a list of parts; Anthropic call here takes text."""
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content if p.get("type") == "text")


def to_anthropic(body: dict) -> dict:
    """Convert an OpenAI chat request body into kwargs for anthropic messages.create."""
    system_parts, messages = [], []
    for m in body["messages"]:
        text = _flatten(m["content"])
        if m["role"] in ("system", "developer"):
            system_parts.append(text)          # Anthropic: system is top-level, not a message
        elif m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": text})
        else:
            raise ValueError(f"unsupported role: {m['role']}")

    # Anthropic requires alternating roles, so merge consecutive same-role messages.
    merged = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n\n" + m["content"]
        else:
            merged.append(dict(m))

    if not merged or merged[0]["role"] != "user":
        raise ValueError("conversation must start with a user message")

    out = {
        "messages": merged,
        # Anthropic requires max_tokens; OpenAI treats it as optional.
        "max_tokens": body.get("max_tokens") or body.get("max_completion_tokens") or DEFAULT_MAX_TOKENS,
    }
    if system_parts:
        out["system"] = "\n\n".join(system_parts)
    if body.get("temperature") is not None:
        out["temperature"] = min(body["temperature"], 1.0)   # OpenAI allows 0-2, Anthropic 0-1
    stop = body.get("stop")
    if stop:
        out["stop_sequences"] = [stop] if isinstance(stop, str) else stop
    return out


def extract_text(resp) -> str:
    """response.content is a list of blocks, not a string."""
    return "".join(b.text for b in resp.content if b.type == "text")


def to_openai(text, model, input_tokens, output_tokens, finish_reason="stop", gateway=None) -> dict:
    """Build an OpenAI-shaped chat.completion response."""
    resp = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": input_tokens,          # Anthropic calls these input_tokens/output_tokens
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }
    if gateway:
        resp["x_gateway"] = gateway
    return resp