"""
Page 8: BCP Chat — AI-powered chat agent for BCP data
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user

st.set_page_config(page_title="BCP Chat", page_icon="💬", layout="wide")
require_login()
render_sidebar_user()

# ─── Custom CSS for modern chat ──────────────────────────────────────────────
st.markdown("""
<style>
    .chat-container {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        margin: 16px 0;
        max-height: 500px;
        overflow-y: auto;
    }
    .chat-msg {
        display: flex; gap: 12px; margin-bottom: 16px;
        animation: fadeIn 0.3s ease-in;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    .chat-avatar {
        width: 36px; height: 36px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 18px; flex-shrink: 0;
    }
    .chat-avatar-user { background: #3b82f6; color: white; }
    .chat-avatar-ai { background: linear-gradient(135deg, #0f172a, #1e3a5f); color: white; }
    .chat-bubble {
        padding: 12px 16px; border-radius: 12px; font-size: 14px;
        line-height: 1.6; max-width: 85%;
    }
    .chat-bubble-user { background: #3b82f6; color: white; border-bottom-right-radius: 4px; margin-left: auto; }
    .chat-bubble-ai { background: white; color: #1e293b; border: 1px solid #e2e8f0; border-bottom-left-radius: 4px; }
    .chat-tools { font-size: 11px; color: #94a3b8; margin-top: 6px; }
    .suggestions { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
</style>
""", unsafe_allow_html=True)

render_page_header("💬", "BCP Chat", "AI-powered assistant — ask anything about fuel, generators, blackouts, prices, BCP scores")

# ─── Chat ─────────────────────────────────────────────────────────────────────
from utils.llm_client import is_llm_available, get_active_model
from agents.chat_agent import chat

# Status
if is_llm_available():
    st.caption(f"🟢 Connected to `{get_active_model()}` — Ask anything about your BCP data")
else:
    st.caption("🟡 No API key — using rule-based responses. Set `OPENROUTER_API_KEY` for full AI.")

# Chat history
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Suggested questions (show only when no history)
if not st.session_state["chat_history"]:
    st.markdown("#### Ask me anything about your BCP data:")
    suggestions = [
        "Which sites have less than 3 days of fuel?",
        "Compare fuel efficiency across all sectors",
        "What will diesel prices be next week?",
        "Give me a BCP risk summary",
        "Which generators are underperforming?",
        "What are the top 5 most urgent sites?",
    ]
    cols = st.columns(3)
    for i, q in enumerate(suggestions):
        with cols[i % 3]:
            if st.button(q, key=f"suggest_{i}", use_container_width=True):
                st.session_state["_pending_question"] = q
                st.rerun()

# Display chat history
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🛡️"):
        st.markdown(msg["content"])
        if msg.get("tools"):
            with st.expander(f"🔧 {len(msg['tools'])} tools used"):
                for t in msg["tools"]:
                    st.caption(f"**{t['tool']}** → {t['result_preview'][:80]}...")

# Chat input
user_input = st.chat_input("Ask about fuel, generators, blackouts, prices, BCP scores...")

# Check for suggestion click
if "_pending_question" in st.session_state:
    user_input = st.session_state.pop("_pending_question")

if user_input:
    # Add user message
    st.session_state["chat_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # AI response
    with st.chat_message("assistant", avatar="🛡️"):
        with st.spinner("🧠 Thinking..."):
            result = chat(user_input, st.session_state["chat_history"][:-1])

        if result["error"]:
            st.error(f"Error: {result['error']}")
            response = f"Sorry, I encountered an error: {result['error']}"
        else:
            response = result["response"] or "I couldn't generate a response."

        st.markdown(response)

        if result["tool_calls"]:
            with st.expander(f"🔧 {len(result['tool_calls'])} tools used"):
                for tc in result["tool_calls"]:
                    st.caption(f"**{tc['tool']}** → {tc['result_preview'][:80]}...")

    st.session_state["chat_history"].append({
        "role": "assistant", "content": response,
        "tools": result.get("tool_calls", []),
    })

# Clear chat
if st.session_state["chat_history"]:
    if st.button("🗑️ Clear Chat", key="clear_chat"):
        st.session_state["chat_history"] = []
        st.rerun()
