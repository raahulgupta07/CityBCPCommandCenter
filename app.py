"""
CityBCPAgent v1 — Home Page
"""
import os
import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from config.settings import DASHBOARD, SECTORS, DB_PATH
from utils.database import get_db
from utils.auth import require_login, render_sidebar_user, get_current_user

st.set_page_config(
    page_title=DASHBOARD["page_title"],
    page_icon=DASHBOARD["page_icon"],
    layout=DASHBOARD["layout"],
    initial_sidebar_state="expanded",
)

require_login()
render_sidebar_user()

user = get_current_user()

# ─── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }

    /* Remove default padding */
    .block-container { padding-top: 1rem !important; }

    /* Nav grid */
    .nav-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0; }
    .nav-item {
        background: white; border: 1px solid #e5e7eb; border-radius: 12px;
        padding: 20px; cursor: pointer; transition: all 0.2s;
        text-decoration: none; display: block;
    }
    .nav-item:hover { border-color: #3b82f6; box-shadow: 0 4px 16px rgba(59,130,246,0.12); transform: translateY(-2px); }
    .nav-icon { font-size: 28px; margin-bottom: 10px; }
    .nav-title { font-size: 15px; font-weight: 600; color: #0f172a; margin-bottom: 4px; }
    .nav-desc { font-size: 12px; color: #64748b; line-height: 1.4; }

    /* Status bar */
    .status-bar {
        display: flex; gap: 24px; padding: 12px 20px;
        background: #f8fafc; border-radius: 10px; border: 1px solid #e2e8f0;
        margin: 16px 0;
    }
    .status-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #475569; }
    .dot { width: 8px; height: 8px; border-radius: 50%; }
    .dot-g { background: #22c55e; }
    .dot-r { background: #ef4444; }
    .dot-y { background: #eab308; }

    /* Quick stats */
    .quick-stats {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0;
    }
    .stat-card {
        background: white; border: 1px solid #e5e7eb; border-radius: 12px;
        padding: 20px; text-align: center;
    }
    .stat-value { font-size: 32px; font-weight: 700; color: #0f172a; }
    .stat-label { font-size: 12px; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)


# ─── Data ────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_kpis():
    with get_db() as conn:
        latest = conn.execute("SELECT MAX(date) as d FROM daily_site_summary").fetchone()["d"]
        if not latest:
            return None

        total_sites = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        total_gens = conn.execute("SELECT COUNT(*) FROM generators WHERE is_active = 1").fetchone()[0]

        # Use date with most data
        best_date = conn.execute(
            "SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()[0]

        reporting = conn.execute(
            "SELECT COUNT(DISTINCT site_id) FROM daily_site_summary WHERE date = ?", (best_date,)
        ).fetchone()[0]

        buf = conn.execute(
            "SELECT SUM(spare_tank_balance) * 1.0 / NULLIF(SUM(total_daily_used), 0) FROM daily_site_summary WHERE date = ?",
            (best_date,)
        ).fetchone()[0]

        fuel = conn.execute(
            "SELECT SUM(total_daily_used) FROM daily_site_summary WHERE date = ?", (best_date,)
        ).fetchone()[0]

        alerts_count = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_acknowledged = 0").fetchone()[0]

        critical = conn.execute(
            "SELECT COUNT(*) FROM daily_site_summary WHERE date = ? AND days_of_buffer < 3 AND days_of_buffer IS NOT NULL",
            (best_date,)
        ).fetchone()[0]

    return {
        "latest": latest, "best_date": best_date, "total_sites": total_sites,
        "total_gens": total_gens, "reporting": reporting,
        "avg_buffer": round(buf, 1) if buf else 0,
        "total_fuel": round(fuel, 0) if fuel else 0,
        "alerts": alerts_count, "critical": critical,
    }

kpis = load_kpis()

# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);border-radius:16px;padding:32px 36px;color:white;margin-bottom:8px">
    <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
            <h1 style="margin:0;font-size:28px;font-weight:700">🛡️ City BCP Agent</h1>
            <p style="margin:6px 0 0;opacity:0.7;font-size:14px">Business Continuity Planning — Generator & Fuel Management</p>
        </div>
        <div style="text-align:right;opacity:0.6;font-size:12px">
            Welcome, <strong>{user['display_name']}</strong><br>
            Data through {kpis['best_date'] if kpis else 'N/A'}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if not kpis:
    st.warning("No data yet. Go to **Data Entry** to upload your Excel files.")
    st.stop()

# ─── Quick Stats ─────────────────────────────────────────────────────────────
buf_color = "#ef4444" if kpis["avg_buffer"] < 3 else "#eab308" if kpis["avg_buffer"] < 7 else "#22c55e"
alert_color = "#ef4444" if kpis["alerts"] > 0 else "#22c55e"
crit_color = "#ef4444" if kpis["critical"] > 0 else "#22c55e"

st.markdown(f"""
<div class="quick-stats">
    <div class="stat-card">
        <div class="stat-value">{kpis['reporting']}<span style="font-size:16px;color:#94a3b8">/{kpis['total_sites']}</span></div>
        <div class="stat-label">Sites Reporting</div>
        <div class="stat-sub">{kpis['total_gens']} generators active</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" style="color:{buf_color}">{kpis['avg_buffer']}</div>
        <div class="stat-label">Avg Buffer Days</div>
        <div class="stat-sub">{'⚠️ Below 7-day target' if kpis['avg_buffer'] < 7 else '✅ Above target'}</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{kpis['total_fuel']:,.0f}<span style="font-size:14px;color:#94a3b8"> L</span></div>
        <div class="stat-label">Fuel Used</div>
        <div class="stat-sub">Latest reporting date</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" style="color:{alert_color}">{kpis['alerts']}</div>
        <div class="stat-label">Active Alerts</div>
        <div class="stat-sub" style="color:{crit_color}">{'🔴 ' + str(kpis['critical']) + ' critical sites' if kpis['critical'] > 0 else '✅ No critical'}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Status Bar ──────────────────────────────────────────────────────────────
db_ok = DB_PATH.exists()
llm_ok = bool(os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
from utils.email_sender import is_email_configured
email_ok = is_email_configured()

st.markdown(f"""
<div class="status-bar">
    <div class="status-item"><span class="dot {'dot-g' if db_ok else 'dot-r'}"></span>Database</div>
    <div class="status-item"><span class="dot {'dot-g' if llm_ok else 'dot-y'}"></span>AI {'Connected' if llm_ok else 'No Key'}</div>
    <div class="status-item"><span class="dot {'dot-g' if email_ok else 'dot-y'}"></span>Email {'Active' if email_ok else 'Not Set'}</div>
    <div class="status-item"><span class="dot dot-g"></span>Data: {kpis['best_date']}</div>
</div>
""", unsafe_allow_html=True)

# ─── Navigation Grid ────────────────────────────────────────────────────────
st.markdown("#### Navigate")

NAV = [
    ("🎯", "Command Center", "Daily decisions, risk scores, alerts, budget", "pages/00_Command_Center.py"),
    ("💰", "Store Economics", "Diesel survival, sales comparison, store open/close", "pages/01_Store_Economics.py"),
    ("🔧", "Operations", "Delivery queue, generators, theft detection, maintenance", "pages/03_Operations.py"),
    ("🏢", "Site Detail", "Deep dive into one store", "pages/02_Site_Detail.py"),
    ("⛽", "Fuel Price", "Price trends, supplier comparison, 7-day forecast", "pages/03_Fuel_Price.py"),
    ("🧠", "AI Assistant", "Ask questions, deep analysis, chat", "pages/08_AI_Insights.py"),
    ("📤", "Data Entry", "Upload Excel files, mapping", "pages/09_Data_Entry.py"),
    ("⚙️", "Settings", "Users, email alerts, data quality", "pages/10_Settings.py"),
]

rows = [NAV[i:i+3] for i in range(0, len(NAV), 3)]
for row in rows:
    cols = st.columns(3)
    for idx, (icon, title, desc, page) in enumerate(row):
        with cols[idx]:
            if st.button(f"{icon} {title}", key=f"nav_{title}", use_container_width=True, help=desc):
                st.switch_page(page)
            st.caption(desc)
