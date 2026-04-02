"""
Page 3: Operations — Tactical execution for ops team.
Merged from: Buffer Risk (04) + Blackout Monitor (05) + Generator Fleet (06) + Decision Board ops sections

6 sections:
1. Delivery Queue (priority fuel deliveries)
2. Generator Fleet Status (all generators)
3. Consumption Variance (theft/waste detection)
4. Maintenance Schedule (service intervals)
5. Blackout Monitor (gen hours as proxy)
6. Anomaly Detection (consumption spikes, idle sites)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
import numpy as np
from utils.database import get_db
from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, finish_page, auto_insight
from utils.echarts import horizontal_bar as ec_hbar, grouped_bar, bar_chart as ec_bar, SECTOR_COLORS, PALETTE
from models.decision_engine import (
    get_delivery_queue, get_generator_failure_risk,
    get_consumption_anomalies, get_load_optimization,
    get_resource_sharing_opportunities,
)
from models.energy_cost import get_generator_detail, get_site_energy_breakdown
from config.settings import SECTORS

st.set_page_config(page_title="Operations", page_icon="🔧", layout="wide")
require_login()
render_sidebar_user()
render_page_header("🔧", "Operations",
    "Tactical view — delivery queue, generators, theft detection, maintenance")

# ─── AUTO AI INSIGHT ──────────────────────────────────────────────────────
queue_preview = get_delivery_queue()
anomaly_preview = get_consumption_anomalies()
auto_insight("Operations",
    f"Delivery queue: {len(queue_preview)} sites need fuel. "
    f"Total liters needed: {queue_preview['liters_needed'].sum():,.0f}. " if not queue_preview.empty else "No deliveries needed. "
    f"Consumption anomalies: {len(anomaly_preview)} sites above normal. " if not anomaly_preview.empty else "No anomalies. "
    f"Check generator variance for theft/waste detection.",
)

# ═══════════════════════════════════════════════════════════════════════════
# 1. DELIVERY QUEUE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🚛 Fuel Delivery Queue")
st.caption("Priority deliveries — sorted by urgency. Exact liters and deadline.")

queue_df = get_delivery_queue()
if not queue_df.empty:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.metric_card(title="Sites Need Fuel", content=str(len(queue_df)), key="op_q1")
    with c2:
        ui.metric_card(title="Total Needed", content=f"{queue_df['liters_needed'].sum():,.0f} L", key="op_q2")
    with c3:
        ui.metric_card(title="Cost", content=f"{queue_df['est_cost'].sum():,.0f} MMK", key="op_q3")
    with c4:
        immediate = len(queue_df[queue_df["urgency"] == "IMMEDIATE"])
        ui.metric_card(title="IMMEDIATE", content=str(immediate),
                       description="send NOW", key="op_q4")

    q_display = queue_df[["site_id", "sector_id", "urgency", "days_of_buffer",
                           "spare_tank_balance", "liters_needed", "delivery_by", "est_cost"]].copy()
    q_display.columns = ["Site", "Sector", "Urgency", "Days Left", "Tank (L)",
                          "Need (L)", "Deliver By", "Cost (MMK)"]
    render_smart_table(q_display, title="Delivery Queue", severity_col="Urgency")

    # Sharing opportunities
    transfers = get_resource_sharing_opportunities()
    if transfers:
        st.markdown("#### Cross-Site Fuel Transfer")
        st.caption("Sites with excess fuel (>14 days) that could supply critical sites")
        t_df = pd.DataFrame(transfers)
        t_df.columns = ["From", "From Sector", "From Buffer", "To", "To Sector",
                         "To Buffer", "Transfer (L)", "Saves Delivery"]
        render_smart_table(t_df, title="Recommended Transfers")
else:
    st.success("All sites have 7+ days of fuel.")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 2. GENERATOR FLEET
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## ⚙️ Generator Fleet Status")

with get_db() as conn:
    fleet = pd.read_sql_query("""
        SELECT g.site_id, s.sector_id, g.model_name, g.power_kva,
               g.consumption_per_hour as rated_L_hr, g.is_active,
               COALESCE(SUM(do.gen_run_hr), 0) as total_hrs,
               COALESCE(SUM(do.daily_used_liters), 0) as total_liters,
               COUNT(DISTINCT do.date) as days
        FROM generators g
        JOIN sites s ON g.site_id = s.site_id
        LEFT JOIN daily_operations do ON g.generator_id = do.generator_id
        WHERE g.is_active = 1
        GROUP BY g.generator_id
        ORDER BY total_hrs DESC
    """, conn)

if not fleet.empty:
    total_gens = len(fleet)
    running = len(fleet[fleet["total_hrs"] > 0])
    idle = total_gens - running

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.metric_card(title="Total Generators", content=str(total_gens), key="op_g1")
    with c2:
        ui.metric_card(title="Running", content=str(running), description="have run hours", key="op_g2")
    with c3:
        ui.metric_card(title="Idle", content=str(idle), description="0 hours logged", key="op_g3")
    with c4:
        total_kva = fleet["power_kva"].sum()
        ui.metric_card(title="Total Capacity", content=f"{total_kva:,.0f} KVA", key="op_g4")

    # Load optimization for multi-gen sites
    load_df = get_load_optimization()
    if not load_df.empty:
        st.markdown("#### Generator Efficiency Ranking (Multi-Gen Sites)")
        st.caption("Which generator to run first for best fuel efficiency (highest KVA per liter)")
        l_display = load_df[["site_id", "model_name", "power_kva", "consumption_per_hour",
                              "kva_per_liter", "rank", "recommendation"]].copy()
        l_display.columns = ["Site", "Generator", "KVA", "L/hr", "KVA/L", "Rank", "Use As"]
        render_smart_table(l_display, title="Load Optimization")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 3. CONSUMPTION VARIANCE (theft/waste detection)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🔍 Consumption Variance — Theft/Waste Detection")
st.caption("Rated capacity × run hours vs actual consumption. High variance = theft, maintenance issue, or wrong specs.")

site_sel = st.selectbox("Select Store", ["All"] + sorted(fleet["site_id"].unique().tolist()) if not fleet.empty else ["All"],
                        key="op_var_site")

if not fleet.empty:
    var_df = fleet.copy()
    if site_sel != "All":
        var_df = var_df[var_df["site_id"] == site_sel]

    var_df["expected_L"] = var_df["rated_L_hr"] * var_df["total_hrs"]
    var_df["variance_L"] = var_df["total_liters"] - var_df["expected_L"]
    var_df["variance_pct"] = np.where(var_df["expected_L"] > 0,
                                       (var_df["variance_L"] / var_df["expected_L"] * 100), 0)
    var_df["status"] = var_df.apply(
        lambda r: "🔴 OVER (+{:.0f}%)".format(r["variance_pct"]) if r["variance_pct"] > 20
        else "🟡 UNDER ({:.0f}%)".format(r["variance_pct"]) if r["variance_pct"] < -20
        else "🟢 NORMAL" if r["expected_L"] > 0 else "⚪ NOT RUNNING", axis=1)

    over = var_df[var_df["variance_pct"] > 20]
    if not over.empty:
        st.error(f"⚠️ **{len(over)} generators** consuming more than rated — possible theft or maintenance issue")

    v_display = var_df[["site_id", "sector_id", "model_name", "power_kva",
                         "total_hrs", "expected_L", "total_liters", "variance_L",
                         "variance_pct", "status"]].copy()
    v_display["variance_pct"] = v_display["variance_pct"].apply(lambda x: f"{x:+.0f}%")
    v_display["variance_L"] = v_display["variance_L"].apply(lambda x: f"{x:+,.0f}" if x != 0 else "—")
    v_display["expected_L"] = v_display["expected_L"].apply(lambda x: f"{x:,.0f}" if x > 0 else "—")
    v_display.columns = ["Site", "Sector", "Generator", "KVA", "Run Hrs",
                          "Expected (L)", "Actual (L)", "Variance (L)", "Var %", "Status"]
    st.dataframe(v_display, use_container_width=True, hide_index=True, height=400)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 4. MAINTENANCE SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🔩 Maintenance Schedule")
st.caption("Service intervals: 500hr, 2000hr, 4000hr, 6000hr")

failure_df = get_generator_failure_risk()
if not failure_df.empty:
    at_risk = failure_df[failure_df["risk_level"].isin(["HIGH", "MEDIUM"])]
    if not at_risk.empty:
        st.warning(f"**{len(at_risk)} generators** need maintenance attention")
        f_display = at_risk[["site_id", "sector_id", "model_name", "total_hours",
                              "risk_level", "next_service_at", "hours_until_service",
                              "maintenance_note"]].head(20).copy()
        f_display.columns = ["Site", "Sector", "Generator", "Total Hrs", "Risk",
                              "Next Service", "Hrs Left", "Note"]
        render_smart_table(f_display, title="Maintenance Alerts", severity_col="Risk")
    else:
        st.success("All generators within safe run-hour limits.")
else:
    st.info("No generator data available.")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 5. BLACKOUT MONITOR
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🔌 Blackout Monitor")
st.caption("Generator run hours as proxy for power outages — high hours = long blackout")

with get_db() as conn:
    blackout = pd.read_sql_query("""
        SELECT dss.site_id, s.sector_id,
               SUM(dss.total_gen_run_hr) as total_hrs,
               AVG(dss.total_gen_run_hr) as avg_daily_hrs,
               MAX(dss.blackout_hr) as max_blackout_hr,
               COUNT(DISTINCT dss.date) as days
        FROM daily_site_summary dss
        JOIN sites s ON dss.site_id = s.site_id
        WHERE dss.total_gen_run_hr > 0
        GROUP BY dss.site_id
        ORDER BY total_hrs DESC
    """, conn)

if not blackout.empty:
    top = blackout.head(15)
    ec_hbar(top["site_id"].tolist(),
            [round(v, 1) for v in top["total_hrs"].tolist()],
            title="Top 15 Sites by Generator Run Hours",
            colors=[SECTOR_COLORS.get(r["sector_id"], "#3b82f6") for _, r in top.iterrows()],
            key="op_bh")

    bo_display = blackout[["site_id", "sector_id", "total_hrs", "avg_daily_hrs", "days"]].copy()
    bo_display["avg_daily_hrs"] = bo_display["avg_daily_hrs"].apply(lambda x: f"{x:.1f}")
    bo_display.columns = ["Site", "Sector", "Total Gen Hrs", "Avg Daily Hrs", "Days"]
    st.dataframe(bo_display, use_container_width=True, hide_index=True)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 6. ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("## 🚩 Anomaly Detection")
st.caption("Sites consuming 30%+ more than 7-day average — possible leaks, extended outages, or theft")

anomalies = get_consumption_anomalies()
if not anomalies.empty:
    st.warning(f"**{len(anomalies)} sites** with abnormal consumption")
    a_display = anomalies[["site_id", "sector_id", "total_daily_used", "avg_7d",
                            "pct_above_avg", "excess_liters", "possible_cause"]].copy()
    a_display.columns = ["Site", "Sector", "Today (L)", "7-Day Avg (L)", "% Above", "Excess (L)", "Possible Cause"]
    render_smart_table(a_display, title="Consumption Anomalies")
else:
    st.success("No consumption anomalies — all sites within normal range.")

finish_page()
