"""AI router — insights + chat WebSocket."""
import asyncio
import json
from typing import Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from utils.ai_agent import morning_briefing, kpi_insight, table_insight, site_insight, executive_briefing
from backend.routers.auth import get_current_user, SECRET_KEY, ALGORITHM
from utils.database import get_db, log_activity

router = APIRouter()


class InsightRequest(BaseModel):
    type: str  # briefing, kpi, table, site
    data: dict
    force_refresh: bool = False


@router.post("/insights")
def get_insight(req: InsightRequest, user: dict = Depends(get_current_user)):
    if req.type == "executive":
        result = executive_briefing(req.data, force_refresh=req.force_refresh)
    elif req.type == "briefing":
        result = morning_briefing(req.data, force_refresh=req.force_refresh)
    elif req.type == "kpi":
        result = kpi_insight(req.data, force_refresh=req.force_refresh)
    elif req.type == "table":
        summary = req.data.get("summary", "")
        table_type = req.data.get("table_type", "sector")
        result = table_insight(summary, table_type, force_refresh=req.force_refresh)
    elif req.type == "site":
        result = site_insight(req.data, force_refresh=req.force_refresh)
    else:
        return {"content": "Unknown insight type"}
    try:
        with get_db() as conn:
            log_activity(conn, user["id"], user["username"], "INSIGHT", "AI", f"Generated {req.type}")
    except Exception:
        pass
    return {"content": result}


@router.get("/chat/history")
def get_chat_history(user: dict = Depends(get_current_user)):
    """Get chat history for current user (last 100 messages)."""
    import json as _json
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, tools TEXT,
            created_at TEXT DEFAULT (datetime('now')))""")
        rows = conn.execute(
            "SELECT role, content, tools, created_at FROM chat_messages WHERE user_id = ? ORDER BY created_at ASC LIMIT 100",
            (user["id"],)
        ).fetchall()
    return [{"role": r[0], "content": r[1], "tools": _json.loads(r[2]) if r[2] else [], "created_at": r[3]} for r in rows]


@router.delete("/chat/history")
def clear_chat_history(user: dict = Depends(get_current_user)):
    """Clear chat history for current user."""
    with get_db() as conn:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user["id"],))
    return {"status": "cleared"}


def _chat_streaming(user_message, conversation_history, progress_callback):
    """
    Run chat agent with real-time progress callbacks for each tool call.
    Returns same dict as chat_fn but sends progress along the way.
    """
    from utils.llm_client import call_llm, is_llm_available
    from agents.config import MAX_TURNS, MAX_TOKENS, TEMPERATURE
    from agents.tools.registry import get_all_tools, execute_tool
    from agents.chat_agent import SYSTEM_PROMPT, _rule_based_response

    if not is_llm_available():
        return _rule_based_response(user_message)

    schemas, _ = get_all_tools()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    tool_calls_made = []

    for turn in range(MAX_TURNS):
        progress_callback({"step": "llm", "turn": turn + 1, "message": "Thinking..."})
        result = call_llm(messages, tools=schemas, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)

        if "error" in result:
            return {"response": None, "tool_calls": tool_calls_made, "error": result["error"]}

        try:
            msg = result["choices"][0]["message"]
        except (KeyError, IndexError):
            return {"response": None, "tool_calls": tool_calls_made, "error": "Unexpected LLM response"}

        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            return {"response": msg.get("content", ""), "tool_calls": tool_calls_made, "error": None}

        # Clean assistant message before appending — remove Gemini-specific fields
        clean_msg = {"role": "assistant", "content": msg.get("content") or ""}
        if tool_calls:
            clean_msg["tool_calls"] = [
                {"id": tc.get("id", tc.get("function", {}).get("name", "")), "type": "function", "function": tc.get("function", {})}
                for tc in tool_calls
            ]
        messages.append(clean_msg)

        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            tool_args = func.get("arguments", "{}")

            progress_callback({"step": "tool", "tool": tool_name, "turn": turn + 1})

            tool_result = execute_tool(tool_name, tool_args)
            tool_calls_made.append({"tool": tool_name, "args": tool_args, "result_preview": tool_result[:200]})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", tool_name),
                "content": tool_result,
            })

    return {"response": "I ran out of processing steps. Please try a simpler question.", "tool_calls": tool_calls_made, "error": None}


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()

    # Authenticate via token query param
    token = websocket.query_params.get("token", "")
    user_id = None
    if token:
        try:
            from jose import jwt as _jwt
            payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = int(payload.get("sub", 0))
        except Exception:
            user_id = None

    history = []

    # Load existing chat history from DB
    if user_id is not None:
        import json as _json
        with get_db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                role TEXT NOT NULL, content TEXT NOT NULL, tools TEXT,
                created_at TEXT DEFAULT (datetime('now')))""")
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY created_at ASC LIMIT 50",
                (user_id,)
            ).fetchall()
            history = [{"role": r[0], "content": r[1]} for r in rows]

    loop = asyncio.get_event_loop()

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                progress_queue = asyncio.Queue()

                def on_progress(data):
                    loop.call_soon_threadsafe(progress_queue.put_nowait, data)

                chat_task = loop.run_in_executor(
                    None, _chat_streaming, msg, list(history), on_progress
                )

                while True:
                    done = chat_task.done()
                    while not progress_queue.empty():
                        try:
                            progress = progress_queue.get_nowait()
                            await websocket.send_json({"type": "thinking", **progress})
                        except asyncio.QueueEmpty:
                            break
                    if done:
                        break
                    await asyncio.sleep(0.1)

                while not progress_queue.empty():
                    try:
                        progress = progress_queue.get_nowait()
                        await websocket.send_json({"type": "thinking", **progress})
                    except asyncio.QueueEmpty:
                        break

                result = chat_task.result()
                response = result.get("response") or ""
                tools = result.get("tool_calls") or []
                error = result.get("error")

                if error:
                    await websocket.send_json({"type": "error", "content": error})
                else:
                    history.append({"role": "user", "content": msg})
                    history.append({"role": "assistant", "content": response})

                    # Save to DB per user
                    if user_id is not None:
                        import json as _json
                        tools_json = _json.dumps([{"tool": t["tool"], "preview": t.get("result_preview", "")[:120]} for t in tools]) if tools else None
                        with get_db() as conn:
                            conn.execute("INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)", (user_id, msg))
                            conn.execute("INSERT INTO chat_messages (user_id, role, content, tools) VALUES (?, 'assistant', ?, ?)", (user_id, response, tools_json))
                            try:
                                # Get username from token payload
                                _username = "unknown"
                                try:
                                    from jose import jwt as _jwt2
                                    _payload = _jwt2.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                                    _username = _payload.get("username", "unknown")
                                except Exception:
                                    pass
                                log_activity(conn, user_id, _username, "CHAT", "AI", f"Chat: {msg[:100]}")
                            except Exception:
                                pass

                    await websocket.send_json({
                        "type": "message",
                        "content": response,
                        "tools": [{"tool": t["tool"], "preview": t.get("result_preview", "")[:120]} for t in tools],
                    })
            except ImportError:
                await websocket.send_json({"type": "message", "content": f"Chat agent not available. You said: {msg}", "tools": []})
            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})
    except WebSocketDisconnect:
        pass
