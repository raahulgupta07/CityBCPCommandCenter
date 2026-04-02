"""
Page 12: Store Economics — War Crisis Dashboard
Tabs: Overall | CFC | CMHL | CP
Each tab: Survival KPIs → Store Decision Table → Generator Detail → Trends → Sales vs Diesel → AI Insights
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
import numpy as np
import json
import re
from utils.database import get_db
from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
from utils.ai_insights import render_insight_panel, finish_page, auto_insight
from utils.echarts import (
    bar_chart as ec_bar, grouped_bar, stacked_bar, line_chart as ec_line,
    dual_axis_chart, pie_chart as ec_pie, horizontal_bar as ec_hbar,
    SECTOR_COLORS, PALETTE,
)
from config.settings import SECTORS, ENERGY_DECISION
from models.energy_cost import (
    get_store_economics, get_store_decision_summary,
    get_generator_detail, get_mapping_status, get_trends,
)

st.set_page_config(page_title="Store Economics", page_icon="💰", layout="wide")
require_login()
render_sidebar_user()

render_page_header("💰", "Store Economics",
    "Diesel cost & survival dashboard — which stores to keep open, where to send fuel")

# ─── Check data ──────────────────────────────────────────────────────────
with get_db() as conn:
    has_energy = conn.execute("SELECT COUNT(*) FROM daily_site_summary").fetchone()[0]
    has_sales = conn.execute("SELECT COUNT(*) FROM daily_sales").fetchone()[0]

if not has_energy:
    st.warning("No diesel data. Upload blackout Excel files via **Data Entry**.")
    st.stop()

# ─── Date filter ─────────────────────────────────────────────────────────
with get_db() as conn:
    dr = conn.execute("SELECT MIN(date), MAX(date) FROM daily_site_summary").fetchone()
col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input("From", value=pd.to_datetime(dr[0]) if dr[0] else None, key="se_from") if dr[0] else None
with col2:
    date_to = st.date_input("To", value=pd.to_datetime(dr[1]) if dr[1] else None, key="se_to") if dr and dr[1] else None
str_from = str(date_from) if date_from else None
str_to = str(date_to) if date_to else None

# ═══════════════════════════════════════════════════════════════════════════
# TABS: Overall | CFC | CMHL | CP
# ═══════════════════════════════════════════════════════════════════════════
sector_tabs = ["Overall"] + sorted(SECTORS.keys())
selected_tab = ui.tabs(options=sector_tabs, default_value="Overall", key="sector_tabs")
sec_filter = None if selected_tab == "Overall" else selected_tab


def render_tab(sec_filter, tk):
    """Render full scrolling content for a sector tab."""

    econ = get_store_economics(date_from=str_from, date_to=str_to)
    if econ.empty:
        st.info("No diesel data.")
        return
    if sec_filter:
        econ = econ[econ["sector_id"] == sec_filter]
        if econ.empty:
            st.info(f"No data for {sec_filter}.")
            return

    label = f"{sec_filter} — {SECTORS.get(sec_filter, {}).get('name', '')}" if sec_filter else "All Sectors"
    matched = econ[econ["has_sales"] == True]
    unmatched = econ[econ["has_sales"] == False]

    # ═══════════════════════════════════════════════════════════════
    # 1. SURVIVAL KPIs
    # ═══════════════════════════════════════════════════════════════
    st.markdown(f"## 🚨 Survival Status — {label}")

    # Only count sites that have BOTH tank data AND daily burn > 0 for days calculation
    has_burn = econ[(econ["avg_daily_liters"].notna()) & (econ["avg_daily_liters"] > 0)
                    & (econ["diesel_available"].notna()) & (econ["diesel_available"] > 0)]
    no_burn = econ[~econ.index.isin(has_burn.index)]

    total_tank = has_burn["diesel_available"].sum() if not has_burn.empty else 0
    total_burn = has_burn["avg_daily_liters"].sum() if not has_burn.empty else 0
    system_days = (total_tank / total_burn) if total_burn > 0 else None
    sites_counted = len(has_burn)
    sites_no_input = len(no_burn)

    critical = len(has_burn[has_burn["latest_buffer_days"] < 3])
    warning = len(has_burn[(has_burn["latest_buffer_days"] >= 3) & (has_burn["latest_buffer_days"] < 7)])
    safe = len(has_burn[has_burn["latest_buffer_days"] >= 7])
    no_data = sites_no_input  # sites with no burn data — can't calculate days

    # Diesel needed to bring critical/warning sites to 7-day buffer (only sites with burn data)
    need_fuel = has_burn.copy()
    need_fuel["need"] = need_fuel.apply(
        lambda r: max(0, (7 * r["avg_daily_liters"]) - r["diesel_available"]), axis=1)
    need_fuel = need_fuel[need_fuel["need"] > 0]
    diesel_needed = need_fuel["need"].sum()

    # Fuel price
    with get_db() as conn:
        price_row = conn.execute("SELECT AVG(price_per_liter) FROM fuel_purchases WHERE price_per_liter IS NOT NULL").fetchone()
        price_map = dict(conn.execute("""
            SELECT sector_id, AVG(price_per_liter) FROM fuel_purchases
            WHERE price_per_liter IS NOT NULL GROUP BY sector_id
        """).fetchall())
    fuel_price = price_row[0] if price_row and price_row[0] else 0
    cost_needed = diesel_needed * fuel_price

    # KPI row 1: Survival
    days_color = "#dc2626" if system_days and system_days < 3 else "#d97706" if system_days and system_days < 7 else "#16a34a"
    st.markdown(f"""
    <div style="display:flex;gap:12px;margin:8px 0">
        <div style="flex:1;background:{days_color};color:white;border-radius:12px;padding:20px;text-align:center">
            <div style="font-size:36px;font-weight:800">{f'{system_days:.1f}' if system_days else '—'}</div>
            <div style="font-size:13px;opacity:0.9">DAYS OF DIESEL LEFT</div>
            <div style="font-size:11px;opacity:0.7">{total_tank:,.0f}L ÷ {total_burn:,.0f}L/day ({sites_counted} sites with data)</div>
        </div>
        <div style="flex:1;background:#1e293b;color:white;border-radius:12px;padding:20px;text-align:center">
            <div style="font-size:36px;font-weight:800">{total_tank:,.0f}</div>
            <div style="font-size:13px;opacity:0.9">TOTAL DIESEL (L)</div>
            <div style="font-size:11px;opacity:0.7">across {len(econ)} sites</div>
        </div>
        <div style="flex:1;background:#1e293b;color:white;border-radius:12px;padding:20px;text-align:center">
            <div style="font-size:36px;font-weight:800">{total_burn:,.0f}</div>
            <div style="font-size:13px;opacity:0.9">DAILY BURN RATE (L)</div>
            <div style="font-size:11px;opacity:0.7">{total_burn * fuel_price:,.0f} MMK/day</div>
        </div>
        <div style="flex:1;background:#7c3aed;color:white;border-radius:12px;padding:20px;text-align:center">
            <div style="font-size:36px;font-weight:800">{diesel_needed:,.0f}</div>
            <div style="font-size:13px;opacity:0.9">DIESEL NEEDED (L)</div>
            <div style="font-size:11px;opacity:0.7">{cost_needed:,.0f} MMK to reach 7-day buffer</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # KPI row 2: Store status + sales
    avg_epct = matched["energy_pct"].mean() if not matched.empty else 0
    st.markdown(f"""
    <div style="display:flex;gap:12px;margin:8px 0">
        <div style="flex:1;background:#dc2626;color:white;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:28px;font-weight:700">{critical}</div>
            <div style="font-size:11px">CRITICAL (&lt;3 days)</div>
        </div>
        <div style="flex:1;background:#d97706;color:white;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:28px;font-weight:700">{warning}</div>
            <div style="font-size:11px">WARNING (3-7 days)</div>
        </div>
        <div style="flex:1;background:#16a34a;color:white;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:28px;font-weight:700">{safe}</div>
            <div style="font-size:11px">SAFE (&gt;7 days)</div>
        </div>
        <div style="flex:1;background:#6b7280;color:white;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:28px;font-weight:700">{no_data}</div>
            <div style="font-size:11px">NO BURN DATA</div>
        </div>
        <div style="flex:1;background:#1e40af;color:white;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:28px;font-weight:700">{len(matched)}/{len(econ)}</div>
            <div style="font-size:11px">MAPPED TO SALES</div>
        </div>
        <div style="flex:1;background:#0f766e;color:white;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:28px;font-weight:700">{avg_epct:.2f}%</div>
            <div style="font-size:11px">AVG DIESEL % OF SALES</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ─── AUTO AI INSIGHT ──────────────────────────────────────────
    auto_insight(f"Store Economics — {label}",
        f"Sites: {len(econ)}, Matched to sales: {len(matched)}, "
        f"Critical (<3d): {critical}, Warning (3-7d): {warning}, Safe: {safe}, No burn data: {no_data}. "
        f"System days left: {f'{system_days:.1f}' if system_days else 'unknown'}. "
        f"Diesel needed: {diesel_needed:,.0f}L ({cost_needed:,.0f} MMK). "
        f"Avg diesel % of sales (matched): {avg_epct:.2f}%. "
        f"Top energy consumers: {', '.join(econ.head(3)['site_id'].tolist())}.",
        cache_key=f"auto_store_econ_{tk}")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # 2. DECISION MATRIX — BY SECTOR (each sector gets its own table)
    # ═══════════════════════════════════════════════════════════════
    st.markdown(f"## 🎯 Decision Matrix — {label}")
    st.caption("Each sector shown separately. Sorted by **diesel % of sales** (worst first). "
               "Diesel Cost and Sales are **totals for the period**. Diesel% = Total Diesel Cost ÷ Total Sales × 100.")

    # Sort globally for action generation
    econ_matched = econ[econ["has_sales"] == True].sort_values("energy_pct", ascending=False, na_position="last")
    econ_unmatched = econ[econ["has_sales"] != True].sort_values("latest_buffer_days", ascending=True, na_position="last")
    econ_sorted = pd.concat([econ_matched, econ_unmatched], ignore_index=True)

    # Generate actions using LLM (cached in DB)
    from utils.ai_insights import _get_cached, _save_cache
    from utils.llm_client import call_llm_simple, is_llm_available

    # AI Actions — fallback logic (LLM runs per-sector with button below)
    def _fallback_action(r):
        burn = r.get("avg_daily_liters") or 0
        tank = r.get("diesel_available") or 0
        dpct = r.get("energy_pct")
        ly_pct = r.get("ly_diesel_pct_of_sales")
        if burn <= 0:
            return "⚪ No burn data"
        if tank <= 0:
            return "🔴 Tank empty — send fuel"
        buf = tank / burn
        action = ""
        if buf < 3:
            action = f"🔴 {buf:.1f}d left"
        elif buf < 7:
            action = f"🟡 {buf:.1f}d left"
        else:
            action = f"🟢 {buf:.0f}d OK"
        # Add diesel% context if available
        if pd.notna(dpct) and dpct > 5:
            action += " | diesel% HIGH"
        if pd.notna(dpct) and pd.notna(ly_pct) and ly_pct > 0 and (dpct - ly_pct) > 2:
            action += " | ⚠️ worse than LY"
        return action

    action_cache_key = f"actions_{tk}_{len(econ_sorted)}"
    cached_actions, _ = _get_cached(action_cache_key)

    if cached_actions:
        try:
            action_map = json.loads(cached_actions)
            econ_sorted["action"] = econ_sorted["site_id"].map(action_map).fillna("—")
        except Exception:
            econ_sorted["action"] = econ_sorted.apply(_fallback_action, axis=1)
    else:
        econ_sorted["action"] = econ_sorted.apply(_fallback_action, axis=1)

    # Calculate margin %
    econ_sorted["margin_pct"] = np.where(
        econ_sorted["total_sales"].notna() & (econ_sorted["total_sales"] > 0),
        (econ_sorted["total_margin"] / econ_sorted["total_sales"] * 100),
        None
    )
    # Calculate daily diesel cost
    econ_sorted["daily_diesel_cost"] = econ_sorted.apply(
        lambda r: (r["avg_daily_liters"] or 0) * price_map.get(r["sector_id"], fuel_price), axis=1
    )
    # LY comparison — get LY diesel % of sales (pct_on_sales)
    with get_db() as conn:
        ly_df = pd.read_sql_query("""
            SELECT s.site_id, de.daily_avg_expense_mmk as ly_daily_mmk,
                   de.pct_on_sales as ly_diesel_pct_of_sales
            FROM sites s
            JOIN diesel_expense_ly de ON s.cost_center_code = de.cost_center_code
        """, conn)
    if not ly_df.empty:
        econ_sorted = econ_sorted.merge(ly_df, on="site_id", how="left")
        # Variance: current diesel% vs LY diesel% (positive = worse now)
        econ_sorted["diesel_pct_change"] = np.where(
            econ_sorted["energy_pct"].notna() & econ_sorted["ly_diesel_pct_of_sales"].notna() & (econ_sorted["ly_diesel_pct_of_sales"] > 0),
            econ_sorted["energy_pct"] - econ_sorted["ly_diesel_pct_of_sales"],
            None
        )
    else:
        econ_sorted["ly_daily_mmk"] = None
        econ_sorted["ly_diesel_pct_of_sales"] = None
        econ_sorted["diesel_pct_change"] = None

    # Compute avg daily sales for matched sites
    econ_sorted["avg_daily_sales"] = np.where(
        econ_sorted["total_sales"].notna() & (econ_sorted["energy_days"] > 0),
        econ_sorted["total_sales"] / econ_sorted["energy_days"],
        None
    )
    econ_sorted["avg_daily_margin"] = np.where(
        econ_sorted["total_margin"].notna() & (econ_sorted["energy_days"] > 0),
        econ_sorted["total_margin"] / econ_sorted["energy_days"],
        None
    )

    # Show per-sector tables with KPIs on top
    sectors_to_show = [sec_filter] if sec_filter else sorted(econ_sorted["sector_id"].unique())

    for sector in sectors_to_show:
        sec_name = SECTORS.get(sector, {}).get("name", sector)
        sec_econ = econ_sorted[econ_sorted["sector_id"] == sector]
        sec_matched = sec_econ[sec_econ["has_sales"] == True]

        if sec_econ.empty:
            continue

        st.markdown(f"### {sector} — {sec_name}")

        # Sector KPIs
        s_sites = len(sec_econ)
        s_gens = sec_econ["num_generators"].sum()
        s_total_diesel = sec_econ["energy_cost"].sum()
        s_total_sales = sec_matched["total_sales"].sum() if not sec_matched.empty else 0
        s_diesel_pct = (s_total_diesel / s_total_sales * 100) if s_total_sales > 0 else None
        s_total_margin = sec_matched["total_margin"].sum() if not sec_matched.empty else 0
        s_margin_pct = (s_total_margin / s_total_sales * 100) if s_total_sales > 0 else None
        s_days = sec_econ["energy_days"].max() if sec_econ["energy_days"].notna().any() else 0
        s_avg_diesel = s_total_diesel / s_days if s_days > 0 else 0
        s_avg_sales = s_total_sales / s_days if s_days > 0 else 0
        s_critical = len(sec_econ[(sec_econ["latest_buffer_days"].notna()) & (sec_econ["latest_buffer_days"] < 3)])

        # Row 1: Sites, Gens, Total Sales, Total Diesel
        r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
        with r1c1:
            ui.metric_card(title="Sites", content=str(s_sites),
                           description=f"{s_gens} generators | {len(sec_matched)} with sales",
                           key=f"dm_sites_{sector}_{tk}")
        with r1c2:
            ui.metric_card(title="Total Sales", content=f"{s_total_sales/1e6:,.1f}M" if s_total_sales > 0 else "—",
                           description=f"Avg: {s_avg_sales/1e6:,.1f}M/day" if s_avg_sales > 0 else "no sales data",
                           key=f"dm_s_{sector}_{tk}")
        with r1c3:
            ui.metric_card(title="Diesel % of Sales", content=f"{s_diesel_pct:.2f}%" if s_diesel_pct else "—",
                           description=f"Diesel: {s_total_diesel/1e6:,.1f}M | {s_avg_diesel/1e6:,.2f}M/day",
                           key=f"dm_d_{sector}_{tk}")
        with r1c4:
            ui.metric_card(title="Margin %", content=f"{s_margin_pct:.1f}%" if s_margin_pct else "—",
                           description=f"Total: {s_total_margin/1e6:,.1f}M",
                           key=f"dm_m_{sector}_{tk}")
        with r1c5:
            ui.metric_card(title="Critical Sites", content=str(s_critical),
                           description="< 3 days buffer",
                           key=f"dm_c_{sector}_{tk}")

        # Row 2: LY comparison
        s_ly_pct_avg = sec_econ["ly_diesel_pct_of_sales"].mean() if "ly_diesel_pct_of_sales" in sec_econ.columns and sec_econ["ly_diesel_pct_of_sales"].notna().any() else None
        s_pct_change = (s_diesel_pct - s_ly_pct_avg) if s_diesel_pct and s_ly_pct_avg else None

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1:
            ui.metric_card(title="LY Diesel % of Sales", content=f"{s_ly_pct_avg:.2f}%" if s_ly_pct_avg else "—",
                           description="last 12-month average",
                           key=f"dm_ly_{sector}_{tk}")
        with r2c2:
            change_desc = "⚠️ higher than LY" if s_pct_change and s_pct_change > 0 else "✅ lower than LY" if s_pct_change else ""
            ui.metric_card(title="Change vs LY", content=f"{s_pct_change:+.2f}pp" if s_pct_change is not None else "—",
                           description=change_desc,
                           key=f"dm_lyd_{sector}_{tk}")
        with r2c3:
            ui.metric_card(title="Data Period", content=f"{s_days:.0f} days",
                           description=f"{sec_econ['energy_start'].min()} → {sec_econ['energy_end'].max()}",
                           key=f"dm_per_{sector}_{tk}")

        # Build sector table
        def _days_display(row):
            burn = row.get("avg_daily_liters")
            buf = row.get("latest_buffer_days")
            if pd.isna(burn) or burn is None or burn <= 0:
                return "—"
            if pd.isna(buf) or buf is None:
                tank = row.get("diesel_available")
                if pd.notna(tank) and tank > 0 and burn > 0:
                    return f"{tank/burn:.1f}"
                return "—"
            return f"{buf:.1f}"

        # Date variance remark
        def _date_remark(row):
            e_days = row.get("energy_days") or 0
            s_days = row.get("sales_days")
            if pd.isna(s_days) or s_days is None or s_days == 0:
                return "No sales data"
            s_days = int(s_days)
            e_days = int(e_days)
            if e_days == s_days:
                return ""
            elif e_days > s_days:
                return f"Sales missing {e_days - s_days}d"
            else:
                return f"Diesel missing {s_days - e_days}d"

        sec_tbl = sec_econ[["site_id", "num_generators",
                             "diesel_available", "avg_daily_liters", "latest_buffer_days",
                             "energy_cost", "daily_diesel_cost",
                             "energy_days", "energy_start", "energy_end",
                             "total_sales", "avg_daily_sales", "sales_days",
                             "margin_pct", "energy_pct",
                             "ly_diesel_pct_of_sales", "diesel_pct_change",
                             "action"]].copy()

        sec_tbl["date_remark"] = sec_econ.apply(_date_remark, axis=1)
        sec_tbl["latest_buffer_days"] = sec_econ.apply(_days_display, axis=1)
        sec_tbl["diesel_available"] = sec_tbl["diesel_available"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
        sec_tbl["avg_daily_liters"] = sec_tbl["avg_daily_liters"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
        sec_tbl["energy_cost"] = sec_tbl["energy_cost"].apply(lambda x: f"{x/1e6:,.2f}M" if x > 0 else "—")
        sec_tbl["daily_diesel_cost"] = sec_tbl["daily_diesel_cost"].apply(lambda x: f"{x/1e6:,.2f}M" if x > 0 else "—")
        sec_tbl["energy_days"] = sec_tbl["energy_days"].apply(lambda x: int(x) if pd.notna(x) else "—")
        sec_tbl["energy_start"] = sec_tbl["energy_start"].fillna("—")
        sec_tbl["energy_end"] = sec_tbl["energy_end"].fillna("—")
        sec_tbl["total_sales"] = sec_tbl["total_sales"].apply(lambda x: f"{x/1e6:,.1f}M" if pd.notna(x) and x > 0 else "—")
        sec_tbl["avg_daily_sales"] = sec_tbl["avg_daily_sales"].apply(lambda x: f"{x/1e6:,.1f}M" if pd.notna(x) and x > 0 else "—")
        sec_tbl["sales_days"] = sec_tbl["sales_days"].apply(lambda x: int(x) if pd.notna(x) and x > 0 else "—")
        sec_tbl["margin_pct"] = sec_tbl["margin_pct"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
        sec_tbl["energy_pct"] = sec_tbl["energy_pct"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        sec_tbl["ly_diesel_pct_of_sales"] = sec_tbl["ly_diesel_pct_of_sales"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        # Flag variance: if current diesel% is >2x LY diesel%, flag as warning
        def _variance_flag(row):
            change = row.get("diesel_pct_change")
            if pd.isna(change) or change is None:
                return "—"
            if abs(change) > 2:
                return f"⚠️ {change:+.2f}pp"
            elif abs(change) > 1:
                return f"↗ {change:+.2f}pp"
            else:
                return f"{change:+.2f}pp"
        sec_tbl["diesel_pct_change"] = sec_econ.apply(_variance_flag, axis=1)

        sec_tbl.columns = ["Site", "Gens", "Tank(L)", "Avg Burn/day", "Buffer Days",
                            "Total Diesel Cost", "Diesel Cost/day",
                            "Diesel Data Days", "Data From", "Data To",
                            "Total Sales", "Avg Sales/day", "Sales Data Days",
                            "Profit Margin %", "Diesel % of Sales",
                            "LY Diesel % of Sales", "Change vs LY",
                            "AI Recommendation", "Date Remark"]

        st.dataframe(sec_tbl, use_container_width=True, hide_index=True,
                     height=min(50 + len(sec_tbl) * 35, 450))

        # AI Analysis button per sector
        ai_key = f"dm_ai_{sector}_{tk}"
        from utils.ai_insights import _get_cached, _save_cache
        cached_ai, cached_at = _get_cached(ai_key)

        if cached_ai:
            st.markdown(f"""
            <div style="background:#f0f9ff;border-left:4px solid #3b82f6;padding:12px 16px;
                        border-radius:0 8px 8px 0;margin:8px 0;font-size:13px;line-height:1.6">
                <strong>🧠 AI Analysis — {sector}</strong>
                <span style="font-size:10px;color:#94a3b8;margin-left:8px">{cached_at[:16] if cached_at else ''}</span>
                <br>{cached_ai}
            </div>""", unsafe_allow_html=True)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(f"🧠 {'Refresh' if cached_ai else 'Generate'} AI Insights for {sector}", key=f"btn_ai_{sector}_{tk}"):
                from utils.llm_client import call_llm_simple

                table_text = sec_tbl.to_string(index=False)
                s_above_5 = len(sec_matched[sec_matched["energy_pct"] > 5]) if not sec_matched.empty else 0

                prompt = f"""Analyze {sector} ({sec_name}) — {s_sites} sites, {s_gens} generators. Use ONLY current data from the table. Plain language, bullet points, specific site names and numbers. No consulting jargon.

Current Diesel % of Sales: {f'{s_diesel_pct:.2f}%' if s_diesel_pct else 'N/A'}
Margin %: {f'{s_margin_pct:.1f}%' if s_margin_pct else 'N/A'}
Critical sites (<3 days buffer): {s_critical}
Sites where diesel >5% of sales: {s_above_5}

TABLE:
{table_text}

**What's happening:**
• 3-4 bullets — current diesel%, buffer levels, which sites are worst, total cost

**What needs attention:**
• 3-4 bullets — sites about to run out, sites where diesel% is high, any data gaps or anomalies

**What to do today:**
• 4-5 bullets — for each critical site: deliver X liters, reduce gen hours, or flag for review. Use site names and numbers."""

                with st.spinner(f"Analyzing {sector}..."):
                    response, error = call_llm_simple(prompt, max_tokens=600)
                if response and not error:
                    _save_cache(ai_key, "sector_analysis", response)
                    st.rerun()

        with col_btn2:
            # Generate per-row AI actions
            action_ai_key = f"actions_{sector}_{tk}"
            if st.button(f"🤖 Generate AI Actions for each site in {sector}", key=f"btn_act_{sector}_{tk}"):
                from utils.llm_client import call_llm_simple

                table_text = sec_tbl.to_string(index=False)

                prompt = f"""For EACH site in the table, write a concise action (max 20 words) based on current data only. No historical comparison.

For EACH site, include:
1. Status icon: 🔴 critical | 🟡 warning | 🟢 safe | ⚪ no data
2. What to do: deliver fuel, reduce gen hours, monitor, close
3. Why: reference specific numbers (buffer days, diesel%, margin%, vs LY)

Rules:
- Buffer < 3 days = 🔴 deliver fuel NOW with exact liters needed (7 days × burn - tank)
- Diesel% > 5% of sales = 🔴 reduce gen hours, revenue doesn't justify cost
- Diesel% > LY by 2+pp = 🟡 investigate spike vs last year
- Diesel% < 2% and buffer > 7 = 🟢 healthy
- No sales data = decide on buffer days only
- No burn data = ⚪ audit site

Return ONLY a JSON object: {{"site_id": "action"}}

TABLE:
{table_text}"""

                with st.spinner(f"Generating per-site actions for {sector}..."):
                    response, error = call_llm_simple(prompt, max_tokens=2000)
                if response and not error:
                    try:
                        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
                        if json_match:
                            action_map = json.loads(json_match.group())
                        else:
                            action_map = json.loads(response)
                        _save_cache(action_cache_key, "actions", json.dumps(action_map))
                        st.rerun()
                    except Exception:
                        st.error("Failed to parse AI actions")

        st.markdown("---")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # 3. GENERATOR DETAIL + VARIANCE ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    st.markdown(f"## 🔧 Generator Detail & Consumption Variance — {label}")
    st.caption("Compare rated capacity vs actual consumption. High variance = possible theft, maintenance issue, or wrong specs.")

    site_opts = [f"{r['site_id']} ({r['num_generators']} gens, "
                 f"{'%.1f' % r['latest_buffer_days'] if pd.notna(r['latest_buffer_days']) else '—'} days left)"
                 for _, r in econ_sorted.iterrows()]
    sel = st.selectbox("Select Site", site_opts, key=f"gen_{tk}")
    sel_id = sel.split(" (")[0] if sel else None

    if sel_id:
        # Per-site AI insight
        site_row = econ_sorted[econ_sorted["site_id"] == sel_id].iloc[0] if sel_id in econ_sorted["site_id"].values else None
        if site_row is not None:
            burn = site_row.get("avg_daily_liters") or 0
            tank = site_row.get("diesel_available") or 0
            dpct = f"{site_row['energy_pct']:.2f}%" if pd.notna(site_row.get("energy_pct")) else "no sales"
            ly_pct = f"{site_row['ly_diesel_pct_of_sales']:.2f}%" if pd.notna(site_row.get("ly_diesel_pct_of_sales")) else "—"
            mpct = f"{site_row['margin_pct']:.1f}%" if pd.notna(site_row.get("margin_pct")) else "—"
            buf = f"{site_row['latest_buffer_days']:.1f}" if pd.notna(site_row.get("latest_buffer_days")) else "—"
            sales_day = f"{site_row['avg_daily_sales']/1e6:,.1f}M" if pd.notna(site_row.get("avg_daily_sales")) and site_row["avg_daily_sales"] > 0 else "—"
            diesel_day = f"{site_row['daily_diesel_cost']/1e6:,.2f}M" if site_row.get("daily_diesel_cost", 0) > 0 else "—"

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#1e293b,#334155);border-radius:12px;padding:16px;margin:8px 0;color:white">
                <div style="font-size:16px;font-weight:700">{sel_id}</div>
                <div style="display:flex;gap:24px;margin-top:8px;font-size:13px;flex-wrap:wrap">
                    <div>🛢️ Tank: <strong>{tank:,.0f}L</strong></div>
                    <div>⛽ Burn: <strong>{burn:,.0f}L/day</strong></div>
                    <div>📅 Buffer: <strong>{buf} days</strong></div>
                    <div>💰 Sales/day: <strong>{sales_day}</strong></div>
                    <div>⛽ Diesel/day: <strong>{diesel_day}</strong></div>
                    <div>📊 Diesel%: <strong>{dpct}</strong></div>
                    <div>📈 Margin%: <strong>{mpct}</strong></div>
                    <div>📅 LY Diesel%: <strong>{ly_pct}</strong></div>
                </div>
            </div>""", unsafe_allow_html=True)

            # Per-site AI button
            site_ai_key = f"site_ai_{sel_id}_{tk}"
            cached_site_ai, cached_site_at = _get_cached(site_ai_key)
            if cached_site_ai:
                st.markdown(f"""
                <div style="background:#f0f9ff;border-left:4px solid #3b82f6;padding:12px 16px;
                            border-radius:0 8px 8px 0;margin:8px 0;font-size:13px;line-height:1.6">
                    <strong>🧠 Site Analysis — {sel_id}</strong><br>{cached_site_ai}
                </div>""", unsafe_allow_html=True)

            if st.button(f"🧠 AI Analysis for {sel_id}", key=f"btn_site_ai_{sel_id}_{tk}"):
                from utils.llm_client import call_llm_simple
                prompt = f"""Analyze site {sel_id}. Current data only, plain language, bullet points.

Tank: {tank:,.0f}L | Burn: {burn:,.0f}L/day | Buffer: {buf} days
Sales/day: {sales_day} | Diesel/day: {diesel_day} | Diesel%: {dpct} | Margin%: {mpct}
Generators: {site_row.get('num_generators', 1)}

**Status:** Is this site healthy? Is diesel% eating into margin?
**Risk:** At current burn, when does tank run out? How many liters needed for 7-day buffer?
**Action:** Deliver fuel, reduce gen hours, or flag for review? Be specific with numbers."""
                with st.spinner(f"Analyzing {sel_id}..."):
                    resp, err = call_llm_simple(prompt, max_tokens=400)
                if resp and not err:
                    _save_cache(site_ai_key, "site_analysis", resp)
                    st.rerun()
        gen_df = get_generator_detail(sel_id)
        site_row = econ[econ["site_id"] == sel_id].iloc[0] if sel_id in econ["site_id"].values else None

        if not gen_df.empty:
            # Summary card
            total_gens = len(gen_df)
            running = len(gen_df[gen_df["total_run_hrs"] > 0])
            total_capacity_hr = (gen_df["consumption_per_hour"] * gen_df["total_run_hrs"]).sum()
            total_actual = gen_df["total_liters"].sum()
            total_variance = total_actual - total_capacity_hr if total_capacity_hr > 0 else 0
            var_pct = (total_variance / total_capacity_hr * 100) if total_capacity_hr > 0 else 0
            tank = site_row["diesel_available"] if site_row is not None and pd.notna(site_row["diesel_available"]) else 0
            days_rated = (tank / (total_capacity_hr / gen_df["total_run_hrs"].sum() if gen_df["total_run_hrs"].sum() > 0 else 1)) if tank > 0 and total_capacity_hr > 0 else None
            days_actual = (tank / (total_actual / gen_df[gen_df["total_run_hrs"] > 0]["total_run_hrs"].sum())) if tank > 0 and total_actual > 0 and gen_df[gen_df["total_run_hrs"] > 0]["total_run_hrs"].sum() > 0 else None

            # Get date range for this site
            e_start = site_row["energy_start"] if site_row is not None else "—"
            e_end = site_row["energy_end"] if site_row is not None else "—"
            e_days = int(site_row["energy_days"]) if site_row is not None and pd.notna(site_row["energy_days"]) else 0
            max_days_data = gen_df["days_tracked"].max() if "days_tracked" in gen_df.columns else e_days

            var_color = "#dc2626" if var_pct > 20 else "#d97706" if var_pct > 10 else "#16a34a" if total_capacity_hr > 0 else "#6b7280"
            st.markdown(f"""
            <div style="background:#1e293b;color:white;border-radius:12px;padding:16px;margin:8px 0">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <span style="font-size:18px;font-weight:700">{sel_id}</span>
                        <span style="opacity:0.7;margin-left:12px">{running}/{total_gens} generators running</span>
                    </div>
                    <div style="background:{var_color};padding:6px 14px;border-radius:20px;font-weight:600">
                        Variance: {var_pct:+.0f}%
                    </div>
                </div>
                <div style="display:flex;gap:24px;margin-top:12px;font-size:13px">
                    <div>🛢️ Tank: <strong>{tank:,.0f} L</strong></div>
                    <div>📐 Expected: <strong>{total_capacity_hr:,.0f} L</strong></div>
                    <div>⛽ Actual: <strong>{total_actual:,.0f} L</strong></div>
                    <div>📊 Variance: <strong style="color:{'#ef4444' if total_variance > 0 else '#22c55e'}">{total_variance:+,.0f} L</strong></div>
                    <div>📅 Days left (actual): <strong>{f'{days_actual:.1f}' if days_actual else '—'}</strong></div>
                    <div>📅 Days left (rated): <strong>{f'{days_rated:.1f}' if days_rated else '—'}</strong></div>
                </div>
                <div style="display:flex;gap:24px;margin-top:8px;font-size:12px;opacity:0.7">
                    <div>📆 Data: <strong>{e_start}</strong> → <strong>{e_end}</strong></div>
                    <div>📊 <strong>{e_days} days</strong> of data</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Per-generator table with variance
            gd = gen_df.copy()
            gd["expected_liters"] = gd["consumption_per_hour"] * gd["total_run_hrs"]
            gd["variance_L"] = gd["total_liters"] - gd["expected_liters"]
            gd["variance_pct"] = np.where(gd["expected_liters"] > 0,
                                           (gd["variance_L"] / gd["expected_liters"] * 100), 0)
            gd["status"] = gd.apply(
                lambda r: "🔴 OVER" if r["variance_pct"] > 20
                else "🟡 UNDER" if r["variance_pct"] < -20
                else "🟢 NORMAL" if r["expected_liters"] > 0
                else "⚪ NOT RUNNING", axis=1)

            gd_display = gd[["model_name", "power_kva", "consumption_per_hour",
                              "days_tracked", "total_run_hrs", "expected_liters", "total_liters",
                              "variance_L", "variance_pct", "energy_cost", "status"]].copy()
            gd_display["variance_pct"] = gd_display["variance_pct"].apply(lambda x: f"{x:+.0f}%")
            gd_display["variance_L"] = gd_display["variance_L"].apply(lambda x: f"{x:+,.0f}" if pd.notna(x) and x != 0 else "—")
            gd_display["expected_liters"] = gd_display["expected_liters"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) and x > 0 else "—")
            gd_display["energy_cost"] = gd_display["energy_cost"].apply(lambda x: f"{x:,.0f}")
            gd_display.columns = ["Machine", "KVA", "Rated L/hr", "Days",
                                   "Run Hours", "Expected (L)", "Actual (L)", "Variance (L)",
                                   "Var %", "Cost (MMK)", "Status"]
            st.dataframe(gd_display, use_container_width=True, hide_index=True)

            # Charts
            if len(gen_df) > 1:
                c1, c2 = st.columns(2)
                with c1:
                    # Expected vs Actual bar
                    grouped_bar(gd["model_name"].tolist(),
                                [{"name": "Expected (L)", "data": [round(v) if pd.notna(v) else 0 for v in gd["expected_liters"]], "color": "#3b82f6"},
                                 {"name": "Actual (L)", "data": [round(v) for v in gd["total_liters"]], "color": "#ef4444"}],
                                title="Expected vs Actual Consumption", height=350, key=f"gvar_{tk}")
                with c2:
                    ec_pie([{"name": r["model_name"], "value": round(r["energy_cost"])}
                            for _, r in gen_df.iterrows()],
                           title=f"Cost Split — {sel_id}", key=f"pie_{tk}")

            # Variance explanation
            over_gens = gen_df[gen_df["efficiency_ratio"] > 120]
            if not over_gens.empty:
                st.warning(f"⚠️ **{len(over_gens)} generator(s) consuming more than rated capacity.** "
                          "Possible causes: diesel theft, engine maintenance needed, or incorrect rated specs.")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # 4. TRENDS (Daily / Weekly / Monthly)
    # ═══════════════════════════════════════════════════════════════
    st.markdown(f"## 📈 Trends — {label}")

    tc1, tc2 = st.columns([1, 1])
    with tc1:
        period = st.selectbox("Period", ["Daily", "Weekly", "Monthly"], index=0, key=f"per_{tk}")
    with tc2:
        with get_db() as conn:
            ts = pd.read_sql_query("SELECT DISTINCT s.site_id, s.sector_id FROM sites s "
                 "JOIN daily_site_summary dss ON s.site_id = dss.site_id ORDER BY s.sector_id, s.site_id", conn)
        if sec_filter and not ts.empty:
            ts = ts[ts["sector_id"] == sec_filter]
        ts_opts = ["All Sites"] + [f"{r['site_id']} ({r['sector_id']})" for _, r in ts.iterrows()]
        t_sel = st.selectbox("Site", ts_opts, key=f"tsite_{tk}")

    t_site = None if t_sel == "All Sites" else t_sel.split(" (")[0]

    t = get_trends(site_id=t_site, sector_id=sec_filter, period=period.lower(),
                   date_from=str_from, date_to=str_to, view="aggregated")
    e_df = t["energy"]
    s_df = t["sales"]

    if not e_df.empty:
        dates = e_df["date"].tolist()
        cost = [round(v) if pd.notna(v) else 0 for v in e_df["energy_cost"]]

        # Chart 1: Sales vs Diesel Cost (dual axis)
        if not s_df.empty:
            # Merge sales + diesel by date
            merged_dates = sorted(set(e_df["date"].tolist()) & set(s_df["date"].tolist()))
            if merged_dates:
                sales_vals = []
                diesel_vals = []
                margin_pct_vals = []
                diesel_pct_vals = []
                for d in merged_dates:
                    s_row = s_df[s_df["date"] == d]
                    e_row = e_df[e_df["date"] == d]
                    s_amt = s_row["sales_amt"].sum() if not s_row.empty else 0
                    m_amt = s_row["margin"].sum() if not s_row.empty else 0
                    d_cost = e_row["energy_cost"].sum() if not e_row.empty else 0
                    sales_vals.append(round(s_amt))
                    diesel_vals.append(round(d_cost))
                    margin_pct_vals.append(round(m_amt / s_amt * 100, 1) if s_amt > 0 else 0)
                    diesel_pct_vals.append(round(d_cost / s_amt * 100, 2) if s_amt > 0 else 0)

                dual_axis_chart(merged_dates, sales_vals, diesel_vals,
                                title=f"Sales vs Diesel Cost — {period}",
                                bar_name="Sales (MMK)", line_name="Diesel Cost (MMK)",
                                bar_color="#3b82f6", line_color="#ef4444",
                                height=400, key=f"td_{tk}")

                # Chart 2: Diesel % of Sales + Margin % (the analyst slide)
                ec_line(merged_dates,
                        [{"name": "Diesel % of Sales", "data": diesel_pct_vals, "color": "#ef4444"},
                         {"name": "Margin %", "data": margin_pct_vals, "color": "#22c55e"}],
                        title=f"Diesel % of Sales vs Margin % — {period}",
                        height=350, key=f"tc_{tk}")
        else:
            # No sales — just show diesel trend
            diesel = [round(v) if pd.notna(v) else 0 for v in e_df["daily_used_liters"]]
            ec_bar(dates, diesel, title=f"Diesel Consumed (L) — {period}",
                   color="#ef4444", key=f"tb_{tk}")

        # Top 15: by Diesel % of Sales (not absolute cost)
        if t_site is None and not matched.empty:
            top = matched.sort_values("energy_pct", ascending=False).head(15)
            rc = {"OPEN": "#16a34a", "MONITOR": "#d97706", "REDUCE": "#ea580c", "CLOSE": "#dc2626"}
            ec_hbar(top["site_id"].tolist(),
                    [round(v, 2) for v in top["energy_pct"].tolist()],
                    title=f"Top 15 by Diesel % of Sales (worst first)",
                    colors=[rc.get(r.get("recommendation", ""), "#ef4444") for _, r in top.iterrows()],
                    key=f"th_{tk}")
        elif t_site is None and "site_id" in e_df.columns:
            # No sales match — fallback to absolute cost
            site_totals = e_df.groupby("site_id")["energy_cost"].sum().reset_index().sort_values("energy_cost", ascending=False)
            ec_hbar(site_totals.head(15)["site_id"].tolist(),
                    [round(v) for v in site_totals.head(15)["energy_cost"].tolist()],
                    title=f"Top 15 by Diesel Cost — {period}", key=f"th_{tk}")

        # Per-generator
        if t_site:
            g_t = get_trends(site_id=t_site, period=period.lower(),
                             date_from=str_from, date_to=str_to, view="generator")
            g_df = g_t["energy"]
            if not g_df.empty and "model_name" in g_df.columns:
                gen_names = sorted(g_df["model_name"].unique())
                dates_g = sorted(g_df["date"].unique())
                s_list = []
                for gn in gen_names:
                    gdata = g_df[g_df["model_name"] == gn]
                    vals = [round(gdata[gdata["date"] == d]["daily_used_liters"].sum())
                            if not gdata[gdata["date"] == d].empty else 0 for d in dates_g]
                    s_list.append({"name": gn, "data": vals, "color": PALETTE[len(s_list) % len(PALETTE)]})
                stacked_bar(dates_g, s_list, title=f"Diesel by Generator — {t_site} — {period}",
                            height=400, key=f"tg_{tk}")

        with st.expander(f"View {period.lower()} data"):
            st.dataframe(e_df, use_container_width=True, hide_index=True)
    else:
        st.info("No trend data.")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # 5. SALES vs ENERGY
    # ═══════════════════════════════════════════════════════════════
    st.markdown(f"## 💰 Sales vs Diesel Cost — {label}")

    if not matched.empty:
        tot_sales = matched["total_sales"].sum()
        tot_energy = matched["energy_cost"].sum()
        pct = (tot_energy / tot_sales * 100) if tot_sales > 0 else 0

        c1, c2, c3 = st.columns(3)
        with c1:
            ui.metric_card(title="Sales (matched)", content=f"{tot_sales/1e6:,.1f}M MMK",
                           description=f"{len(matched)} stores, same dates as diesel", key=f"v1_{tk}")
        with c2:
            ui.metric_card(title="Diesel Cost", content=f"{tot_energy/1e6:,.1f}M MMK",
                           description="diesel cost", key=f"v2_{tk}")
        with c3:
            ui.metric_card(title="Diesel %", content=f"{pct:.2f}%",
                           description="cost / sales", key=f"v3_{tk}")

        sorted_m = matched.sort_values("energy_pct", ascending=True)
        rc = {"OPEN": "#16a34a", "MONITOR": "#d97706", "REDUCE": "#ea580c", "CLOSE": "#dc2626"}
        ec_hbar(sorted_m["site_id"].tolist(),
                [round(v, 2) for v in sorted_m["energy_pct"].tolist()],
                title="Diesel Cost as % of Sales per Store",
                colors=[rc.get(r["recommendation"], "#3b82f6") for _, r in sorted_m.iterrows()],
                key=f"vh_{tk}")

        md = matched[["site_id", "diesel_available", "energy_cost", "total_sales",
                       "energy_pct", "energy_days", "sales_days", "date_remark", "recommendation"]].copy()
        md["energy_cost"] = md["energy_cost"].apply(lambda x: f"{x:,.0f}")
        md["total_sales"] = md["total_sales"].apply(lambda x: f"{x:,.0f}")
        md["energy_pct"] = md["energy_pct"].apply(lambda x: f"{x:.2f}%")
        md["diesel_available"] = md["diesel_available"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
        md["sales_days"] = md["sales_days"].apply(lambda x: int(x) if pd.notna(x) else "—")
        md.columns = ["Store", "Tank (L)", "Diesel Cost", "Sales",
                       "Diesel %", "E.Days", "S.Days", "Date Remark", "Decision"]
        st.dataframe(md, use_container_width=True, hide_index=True)
    else:
        st.info("No stores mapped to sales data. Upload `site location mapping.xlsx` via Data Entry.")

    if not unmatched.empty:
        with st.expander(f"⚡ {len(unmatched)} sites without sales data"):
            ud = unmatched[["site_id", "sector_id", "num_generators",
                            "diesel_available", "total_liters", "energy_cost"]].copy()
            ud["diesel_available"] = ud["diesel_available"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
            ud["energy_cost"] = ud["energy_cost"].apply(lambda x: f"{x:,.0f}")
            ud["total_liters"] = ud["total_liters"].apply(lambda x: f"{x:,.0f}")
            ud.columns = ["Store", "Sector", "Gens", "Tank (L)", "Diesel Used", "Diesel Cost"]
            st.dataframe(ud, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # 6. AI INSIGHTS
    # ═══════════════════════════════════════════════════════════════
    st.markdown(f"## 🧠 AI Insights — {label}")

    # Auto-generated text summary
    insights = []
    if critical > 0:
        crit_sites = econ_sorted[econ_sorted["latest_buffer_days"].notna() & (econ_sorted["latest_buffer_days"] < 3)]
        sites_list = ", ".join(crit_sites["site_id"].tolist()[:5])
        insights.append(f"🔴 **{critical} stores have less than 3 days of diesel** — send fuel to: {sites_list}")
    if warning > 0:
        insights.append(f"🟡 **{warning} stores** have 3-7 days — monitor closely, plan delivery this week")
    if diesel_needed > 0:
        insights.append(f"🛢️ **{diesel_needed:,.0f} liters needed** ({cost_needed:,.0f} MMK) to bring all stores to 7-day buffer")
    if system_days and system_days < 7:
        insights.append(f"⏰ **System runs dry in {system_days:.1f} days** at current burn rate")
    if not matched.empty:
        worst = matched.sort_values("energy_pct", ascending=False).iloc[0]
        insights.append(f"💰 **{worst['site_id']}** has highest diesel cost at **{worst['energy_pct']:.2f}%** of sales — "
                       f"{'still viable' if worst['energy_pct'] < 5 else 'consider reducing gen hours'}")
    if no_data > 0:
        insights.append(f"⚪ **{no_data} stores** have no diesel burn input — cannot calculate days left")
    if len(matched) < len(econ):
        insights.append(f"❓ **{len(econ) - len(matched)} stores** have no sales data — cannot evaluate profitability")

    if insights:
        for i in insights:
            st.markdown(i)
    else:
        st.success("All stores are healthy with adequate diesel supply.")

    render_insight_panel(
        f"Crisis dashboard for {label}. {critical} critical, {warning} warning, {safe} safe stores. "
        f"System has {f'{system_days:.1f}' if system_days else 'unknown'} days of diesel left. "
        f"{len(matched)} stores mapped to sales with avg {avg_epct:.2f}% diesel cost.",
        econ.describe().to_dict(), f"ai_{tk}"
    )


# ═══════════════════════════════════════════════════════════════════════════
render_tab(sec_filter, selected_tab.lower())
finish_page()
