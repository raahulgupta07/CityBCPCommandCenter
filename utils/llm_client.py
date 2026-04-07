"""
LLM Client — Supports OpenRouter (multi-model) and Anthropic direct.
Graceful fallback if no API key available.
"""
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from config.settings import AGENT_CONFIG

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── API Key Detection ───────────────────────────────────────────────────────

def _get_openrouter_key():
    return os.environ.get("OPENROUTER_API_KEY", "").strip()

def _get_anthropic_key():
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()

def is_llm_available():
    return bool(_get_openrouter_key() or _get_anthropic_key())

def get_active_provider():
    if _get_openrouter_key():
        return "openrouter"
    if _get_anthropic_key():
        return "anthropic"
    return None

def get_active_model():
    provider = get_active_provider()
    if provider == "openrouter":
        return AGENT_CONFIG["models"]["reasoning"]
    if provider == "anthropic":
        return "claude-sonnet-4-20250514"
    return "rule-based (no API key)"


# ─── OpenRouter Call ─────────────────────────────────────────────────────────

def _call_openrouter(messages, tools=None, model=None, max_tokens=4096, temperature=0.3):
    key = _get_openrouter_key()
    if not key:
        return None

    model = model or AGENT_CONFIG["models"]["reasoning"]
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://city-bcp-agent.local",
        "X-Title": "City BCP Agent",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    # Sanitize messages for OpenRouter/Gemini compatibility
    clean_msgs = []
    for m in messages:
        cm = dict(m)
        # Gemini requires content to be a string, not None
        if cm.get("content") is None:
            cm["content"] = ""
        # Convert role "tool" to format OpenRouter expects
        if cm.get("role") == "tool" and "tool_call_id" in cm:
            cm = {"role": "tool", "tool_call_id": cm["tool_call_id"], "content": str(cm.get("content", ""))}
        clean_msgs.append(cm)
    payload["messages"] = clean_msgs

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=payload, timeout=120,
        )
        if resp.status_code != 200:
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text[:300])
            except Exception:
                err_msg = resp.text[:300]
            return {"error": f"OpenRouter {resp.status_code}: {err_msg}"}
        return resp.json()
    except requests.exceptions.Timeout:
        return {"error": "LLM request timed out (120s). Try a simpler question."}
    except Exception as e:
        return {"error": str(e)}


# ─── Anthropic Direct Call ───────────────────────────────────────────────────

def _call_anthropic(messages, tools=None, model=None, max_tokens=4096, temperature=0.3):
    key = _get_anthropic_key()
    if not key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)

        # Convert OpenAI-format messages to Anthropic format
        system_msg = None
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                api_messages.append({"role": m["role"], "content": m["content"]})

        kwargs = {
            "model": model or "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": api_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            # Convert OpenAI tool format to Anthropic format
            anthropic_tools = []
            for t in tools:
                func = t.get("function", t)
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
            kwargs["tools"] = anthropic_tools

        response = client.messages.create(**kwargs)

        # Convert Anthropic response to OpenAI-compatible format
        text_content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    }
                })

        result_msg = {"content": text_content, "role": "assistant"}
        if tool_calls:
            result_msg["tool_calls"] = tool_calls

        return {"choices": [{"message": result_msg}]}

    except Exception as e:
        return {"error": str(e)}


# ─── Unified Call ────────────────────────────────────────────────────────────

def call_llm(messages, tools=None, model=None, max_tokens=4096, temperature=0.3):
    """
    Call LLM via best available provider.
    Returns OpenAI-compatible response dict or {"error": "..."}.
    """
    provider = get_active_provider()

    if provider == "openrouter":
        result = _call_openrouter(messages, tools, model, max_tokens, temperature)
        if result and "error" not in result:
            return result
        # Fallback to anthropic
        if _get_anthropic_key():
            return _call_anthropic(messages, tools, model, max_tokens, temperature)
        return result or {"error": "OpenRouter call failed"}

    if provider == "anthropic":
        return _call_anthropic(messages, tools, model, max_tokens, temperature)

    return {"error": "No API key configured. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY."}


def call_llm_simple(prompt, system_prompt=None, max_tokens=2048):
    """Simple text-only LLM call (no tools)."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    result = call_llm(messages, max_tokens=max_tokens)
    if "error" in result:
        return None, result["error"]

    try:
        content = result["choices"][0]["message"]["content"]
        return content, None
    except (KeyError, IndexError):
        return None, "Unexpected response format"
