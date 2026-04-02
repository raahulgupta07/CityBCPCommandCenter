"""
Page 0: Command Center — CEO's daily war-room view.
Merged from: Decision Board (00) + BCP Command Center (07) + Sector Overview forecast (01)

8 sections:
1. Survival KPIs
2. Operating Modes (FULL/REDUCED/CLOSE)
3. Delivery Queue (where to send fuel truck)
4. BCP Risk Scores (A-F)
5. 7-Day Stockout Forecast
6. Fuel Price & Budget
7. Active Alerts
8. What-If Simulator
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, finish_page, auto_insight
from utils.kpi_card import render_kpi, render_chart_source
from utils.echarts import horizontal_bar as ec_hbar, bar_chart as ec_bar, SECTOR_COLORS
from models.decision_engine import (
    get_operating_modes, get_delivery_queue,
    get_weekly_budget_forecast, get_supplier_buy_signal, run_what_if,
)
from models.bcp_engine import compute_bcp_scores
from models.buffer_predictor import predict_buffer_depletion, get_critical_sites
from alerts.alert_engine import get_active_alerts
from config.settings import SECTORS

st.set_page_config(page_title="Command Center", page_icon="🎯", layout="wide")
require_login()
render_sidebar_user()
render_page_header("🎯", "Command Center",
    "CEO daily view — operating modes, fuel delivery, risk scores, alerts, budget")

# ═══════════════════════════════════════════════════════════════════════════
# 1. SURVIVAL KPIs
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🚨 Survival Status")

with get_db() as conn:
    latest = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()[0]
    if not latest:
        st.warning("No data. Upload blackout files via **Data Entry**.")
        st.stop()

    # Aggregate all sites
    stats = conn.execute("""
        SELECT COUNT(DISTINCT site_id) as sites,
               SUM(spare_tank_balance) as total_tank,
               SUM(total_daily_used) as total_burn,
               SUM(CASE WHEN days_of_buffer < 3 AND days_of_buffer IS NOT NULL THEN 1 ELSE 0 END) as critical,
               SUM(CASE WHEN days_of_buffer >= 3 AND days_of_buffer < 7 THEN 1 ELSE 0 END) as warning,
               SUM(CASE WHEN days_of_buffer >= 7 THEN 1 ELSE 0 END) as safe
        FROM daily_site_summary
        WHERE date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
    """).fetchone()

    price_row = conn.execute("SELECT AVG(price_per_liter) FROM fuel_purchases WHERE price_per_liter IS NOT NULL").fetchone()
    fuel_price = price_row[0] if price_row and price_row[0] else 0

total_tank = stats["total_tank"] or 0
total_burn = stats["total_burn"] or 0
system_days = (total_tank / total_burn) if total_burn > 0 else None
daily_cost = total_burn * fuel_price

days_color = "#dc2626" if system_days and system_days < 3 else "#d97706" if system_days and system_days < 7 else "#16a34a"

st.markdown(f"""
<div style="display:flex;gap:12px;margin:8px 0">
    <div style="flex:1;background:{days_color};color:white;border-radius:12px;padding:20px;text-align:center">
        <div style="font-size:36px;font-weight:800">{f'{system_days:.1f}' if system_days else '—'}</div>
        <div style="font-size:13px;opacity:0.9">DAYS OF DIESEL LEFT</div>
        <div style="font-size:11px;opacity:0.7">{total_tank:,.0f}L ÷ {total_burn:,.0f}L/day</div>
    </div>
    <div style="flex:1;background:#1e293b;color:white;border-radius:12px;padding:20px;text-align:center">
        <div style="font-size:36px;font-weight:800">{total_tank:,.0f}</div>
        <div style="font-size:13px;opacity:0.9">TOTAL DIESEL (L)</div>
        <div style="font-size:11px;opacity:0.7">{stats['sites']} sites</div>
    </div>
    <div style="flex:1;background:#1e293b;color:white;border-radius:12px;padding:20px;text-align:center">
        <div style="font-size:36px;font-weight:800">{daily_cost:,.0f}</div>
        <div style="font-size:13px;opacity:0.9">DAILY DIESEL COST (MMK)</div>
        <div style="font-size:11px;opacity:0.7">{total_burn:,.0f} L/day × {fuel_price:,.0f}/L</div>
    </div>
</div>
<div style="display:flex;gap:12px;margin:8px 0">
    <div style="flex:1;background:#dc2626;color:white;border-radius:10px;padding:12px;text-align:center">
        <div style="font-size:26px;font-weight:700">{stats['critical']}</div><div style="font-size:11px">CRITICAL (&lt;3d)</div>
    </div>
    <div style="flex:1;background:#d97706;color:white;border-radius:10px;padding:12px;text-align:center">
        <div style="font-size:26px;font-weight:700">{stats['warning']}</div><div style="font-size:11px">WARNING (3-7d)</div>
    </div>
    <div style="flex:1;background:#16a34a;color:white;border-radius:10px;padding:12px;text-align:center">
        <div style="font-size:26px;font-weight:700">{stats['safe']}</div><div style="font-size:11px">SAFE (&gt;7d)</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── AUTO AI INSIGHT ──────────────────────────────────────────────────────
auto_insight("Command Center", f"""
System status: {f'{system_days:.1f}' if system_days else 'unknown'} days of diesel left.
Total tank: {total_tank:,.0f}L, Daily burn: {total_burn:,.0f}L, Daily cost: {daily_cost:,.0f} MMK.
Critical sites (<3 days): {stats['critical']}, Warning (3-7): {stats['warning']}, Safe (>7): {stats['safe']}.
Total sites: {stats['sites']}.
""")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 2. OPERATING MODES
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🎯 Operating Modes")
st.caption("Should each store run full, reduce hours, or close today?")

modes_df = get_operating_modes()
if not modes_df.empty:
    display = modes_df[["site_id", "sector_id", "mode", "days_of_buffer",
                         "spare_tank_balance", "total_daily_used", "daily_fuel_cost", "reason"]].copy()
    display.columns = ["Site", "Sector", "Mode", "Buffer Days", "Tank (L)", "Daily Use (L)", "Daily Cost (MMK)", "Action"]
    render_smart_table(display, title=f"Operating Mode Recommendations ({len(modes_df)} sites)", severity_col="Mode",
                       highlight_cols={"Buffer Days": {"good": "high", "thresholds": [7, 3]}})

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 3. DELIVERY QUEUE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🚛 Fuel Delivery Queue")
st.caption("Where to send the truck — sorted by urgency")

queue_df = get_delivery_queue()
if not queue_df.empty:
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric_card(title="Sites Need Fuel", content=str(len(queue_df)),
                       description="below 7-day buffer", key="dq_cnt")
    with c2:
        ui.metric_card(title="Total Needed", content=f"{queue_df['liters_needed'].sum():,.0f} L",
                       description="to reach 7-day buffer", key="dq_lit")
    with c3:
        ui.metric_card(title="Delivery Cost", content=f"{queue_df['est_cost'].sum():,.0f} MMK",
                       description="estimated", key="dq_cost")

    q_display = queue_df[["site_id", "sector_id", "urgency", "days_of_buffer",
                           "spare_tank_balance", "liters_needed", "delivery_by", "est_cost"]].copy()
    q_display.columns = ["Site", "Sector", "Urgency", "Days Left", "Tank (L)",
                          "Need (L)", "Deliver By", "Cost (MMK)"]
    render_smart_table(q_display, title="Delivery Queue", severity_col="Urgency")
else:
    st.success("All sites have 7+ days of fuel. No deliveries needed.")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 4. BCP RISK SCORES
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🛡️ BCP Risk Scores")
st.caption("A-F grades: Fuel Reserve (35%) + Generator Coverage (30%) + Power Capacity (20%) + Resilience (15%)")

with get_db() as conn:
    best_date = conn.execute("SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    best_date = best_date[0] if best_date else None

if best_date:
    bcp_df = compute_bcp_scores(best_date)
    if not bcp_df.empty:
        # Grade distribution
        grades = bcp_df["grade"].value_counts().to_dict()
        gc1, gc2, gc3, gc4, gc5 = st.columns(5)
        for col, (grade, color) in zip([gc1, gc2, gc3, gc4, gc5],
            [("A", "#16a34a"), ("B", "#2196F3"), ("C", "#d97706"), ("D", "#ea580c"), ("F", "#dc2626")]):
            with col:
                cnt = grades.get(grade, 0)
                st.markdown(f'<div style="background:{color};color:white;border-radius:8px;padding:10px;text-align:center">'
                            f'<span style="font-size:22px;font-weight:700">{grade}: {cnt}</span></div>',
                            unsafe_allow_html=True)

        bcp_display = bcp_df[["site_id", "sector_id", "bcp_score", "grade"]].sort_values("bcp_score").copy()
        bcp_display.columns = ["Site", "Sector", "Score", "Grade"]
        render_smart_table(bcp_display, title="BCP Scores (worst first)", severity_col="Grade")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 5. STOCKOUT FORECAST (7-day)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## ⏰ 7-Day Stockout Forecast")
st.caption("Sites projected to run out of diesel within 7 days")

try:
    critical_df = get_critical_sites(threshold_days=7)
    if not critical_df.empty:
        st.warning(f"**{len(critical_df)} sites** projected to run low within 7 days")
        cs_display = critical_df[["site_id", "sector_id", "current_balance", "smoothed_daily_used",
                                   "days_until_stockout", "projected_stockout_date", "trend", "confidence"]].copy()
        cs_display.columns = ["Site", "Sector", "Tank (L)", "Daily Burn (smoothed)", "Days Left",
                               "Stockout Date", "Trend", "Confidence"]
        render_smart_table(cs_display, title="Critical Stockout Forecast")
    else:
        st.success("No sites projected to run out within 7 days.")
except Exception as e:
    st.info(f"Forecast model needs more data: {e}")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 6. FUEL PRICE & BUDGET
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 💰 Fuel Price & Weekly Budget")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Supplier Buy Signal")
    signal = get_supplier_buy_signal()
    if signal and signal.get("signals"):
        for s in signal["signals"]:
            color = "#16a34a" if s["recommendation"] == "BUY NOW" else "#d97706" if s["recommendation"] == "WAIT" else "#3b82f6"
            st.markdown(f"""
            <div style="background:white;border:1px solid #e5e7eb;border-left:4px solid {color};
                        border-radius:0 10px 10px 0;padding:14px;margin:6px 0">
                <strong>{s['supplier']}</strong> — {s['current_price']:,.0f} MMK/L
                → <strong style="color:{color}">{s['recommendation']}</strong>
            </div>""", unsafe_allow_html=True)

with col2:
    st.markdown("#### Weekly Budget")
    budget = get_weekly_budget_forecast()
    if budget:
        ui.metric_card(title="Weekly Budget", content=f"{budget['total_weekly_cost_mmk']:,.0f} MMK",
                       description=f"{budget['total_weekly_liters']:,.0f} L needed", key="wb")
        if budget["sectors"]:
            budget_df = pd.DataFrame(budget["sectors"])
            budget_df.columns = ["Sector", "Daily (L)", "Weekly (L)", "Price/L", "Weekly Cost"]
            st.dataframe(budget_df, use_container_width=True, hide_index=True)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 7. ACTIVE ALERTS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🚨 Active Alerts")

alerts_df = get_active_alerts()
if not alerts_df.empty:
    for severity, color in [("CRITICAL", "#dc2626"), ("WARNING", "#d97706"), ("INFO", "#3b82f6")]:
        sev_df = alerts_df[alerts_df["severity"] == severity]
        if not sev_df.empty:
            st.markdown(f"**{severity}** ({len(sev_df)})")
            for _, a in sev_df.head(10).iterrows():
                site = a.get("site_id") or a.get("sector_id") or ""
                st.markdown(f'<div style="border-left:3px solid {color};padding:6px 12px;margin:4px 0;font-size:13px">'
                            f'<strong>{site}</strong> — {a["message"]}</div>', unsafe_allow_html=True)
else:
    st.success("No active alerts.")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 8. WHAT-IF SIMULATOR
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🔮 What-If Simulator")
st.caption("See how cost changes with different fuel prices or consumption levels")

wc1, wc2 = st.columns(2)
with wc1:
    price_change = st.slider("Fuel Price Change %", -30, 50, 0, 5, key="wi_price")
with wc2:
    consumption_change = st.slider("Consumption Change %", -30, 50, 0, 5, key="wi_consumption")

whatif = run_what_if(price_change, consumption_change)
if whatif:
    wrc1, wrc2, wrc3 = st.columns(3)
    with wrc1:
        ui.metric_card(title="Current Weekly", content=f"{whatif['base_cost']:,.0f} MMK", key="wi_base")
    with wrc2:
        ui.metric_card(title="Projected", content=f"{whatif['new_cost']:,.0f} MMK",
                       description=f"{'↑' if whatif['pct_change'] > 0 else '↓'} {abs(whatif['pct_change'])}%", key="wi_new")
    with wrc3:
        ui.metric_card(title="Impact", content=f"{'+' if whatif['difference'] > 0 else ''}{whatif['difference']:,.0f} MMK", key="wi_diff")

finish_page()
