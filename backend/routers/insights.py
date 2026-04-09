"""Insights router — operating modes, delivery queue, BCP scores, alerts, fuel intel, recommendations."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
import numpy as np
import pandas as pd
from utils.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter()


def fmtN(v):
    """Format number for narrative: 1.5M, 36.8K, 6,541."""
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.1f}K"
    return f"{v:,.0f}"


def _df(df):
    """Convert a DataFrame (or None) to a list of dicts safe for JSON."""
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return df.fillna("").to_dict(orient="records")


def _enrich_site_code(df):
    """Add site_code (region) column from sites table if df has site_id."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df
    if "site_id" not in df.columns:
        return df
    try:
        with get_db() as conn:
            sites = pd.read_sql_query("SELECT site_id, region as site_code FROM sites", conn)
        df = df.merge(sites, on="site_id", how="left")
        df["site_code"] = df["site_code"].fillna("")
    except Exception:
        if "site_code" not in df.columns:
            df["site_code"] = ""
    return df


def _sanitize(obj):
    """Recursively replace NaN/Inf floats with 0 so JSON serialization never fails."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    # numpy scalar
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return 0
        return v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


# ---------- 5. Recommendations ----------

@router.get("/recommendations")
def recommendations(user: dict = Depends(get_current_user)):
    try:
        recs = []
        with get_db() as conn:
            # Critical sites — buffer < 3 days
            crit = pd.read_sql_query(
                """SELECT site_id, buffer_days
                   FROM daily_site_summary
                   WHERE buffer_days IS NOT NULL AND buffer_days < 3
                   ORDER BY buffer_days""",
                conn,
            )
            if not crit.empty:
                recs.append({
                    "type": "critical",
                    "title": "Critical Buffer Sites",
                    "message": f"{len(crit)} site(s) have less than 3 days of fuel buffer remaining.",
                    "sites": crit["site_id"].tolist(),
                })

            # Burn spikes — daily_used > 7-day avg * 1.3
            burn = pd.read_sql_query(
                """SELECT d.site_id, d.total_daily_used,
                          AVG(d2.total_daily_used) AS avg_7d
                   FROM daily_operations d
                   JOIN daily_operations d2
                        ON d2.site_id = d.site_id
                       AND d2.date BETWEEN date(d.date, '-7 days') AND d.date
                   WHERE d.date = (SELECT MAX(date) FROM daily_operations)
                   GROUP BY d.site_id
                   HAVING d.total_daily_used > avg_7d * 1.3""",
                conn,
            )
            if not burn.empty:
                recs.append({
                    "type": "warning",
                    "title": "Burn Rate Spike",
                    "message": f"{len(burn)} site(s) are burning fuel 30%+ above their 7-day average.",
                    "sites": burn["site_id"].tolist(),
                })

            # Rising diesel % sites
            diesel_pct = pd.read_sql_query(
                """SELECT s.site_id,
                          s.diesel_cost, s.total_sales
                   FROM daily_site_summary s
                   WHERE s.total_sales > 0
                     AND (s.diesel_cost / s.total_sales) > 0.10
                   ORDER BY (s.diesel_cost / s.total_sales) DESC""",
                conn,
            )
            if not diesel_pct.empty:
                recs.append({
                    "type": "warning",
                    "title": "Rising Diesel % of Sales",
                    "message": f"{len(diesel_pct)} site(s) have diesel cost exceeding 10% of sales.",
                    "sites": diesel_pct["site_id"].tolist(),
                })

            # Efficiency anomalies
            eff = pd.read_sql_query(
                """SELECT site_id
                   FROM daily_operations
                   WHERE gen_hours > 0
                     AND (total_daily_used / gen_hours) > 50
                   GROUP BY site_id""",
                conn,
            )
            if not eff.empty:
                recs.append({
                    "type": "info",
                    "title": "Efficiency Anomalies",
                    "message": f"{len(eff)} site(s) show unusually high fuel consumption per generator hour.",
                    "sites": eff["site_id"].tolist(),
                })

        return {"recommendations": recs}
    except Exception:
        return {"recommendations": []}


# ---------- 6. Active Alerts ----------

@router.get("/alerts/active")
def active_alerts(
    severity: Optional[str] = Query(None),
    sector_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    try:
        from alerts.alert_engine import get_active_alerts
        result = get_active_alerts(severity=severity, sector_id=sector_id)
        records = _df(result)

        counts = {"critical": 0, "warning": 0, "info": 0}
        if isinstance(result, pd.DataFrame) and not result.empty:
            sev_counts = result["severity"].str.lower().value_counts().to_dict()
            for k in counts:
                counts[k] = sev_counts.get(k, 0)

        return {"alerts": records, "counts": counts}
    except Exception:
        return {"alerts": [], "counts": {"critical": 0, "warning": 0, "info": 0}}


# ---------- 7. Fuel Intel ----------

@router.get("/fuel-intel")
def fuel_intel(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_supplier_buy_signal, get_weekly_budget_forecast
        from models.fuel_price_forecast import forecast_fuel_price

        signal_result = get_supplier_buy_signal()
        budget_result = get_weekly_budget_forecast()

        raw_forecast = forecast_fuel_price()
        # Convert any DataFrames inside forecast result to lists
        forecast_result = {}
        if isinstance(raw_forecast, dict):
            for k, v in raw_forecast.items():
                if isinstance(v, pd.DataFrame):
                    forecast_result[k] = _df(v)
                else:
                    forecast_result[k] = v
        else:
            forecast_result = raw_forecast

        # Purchase log
        log = pd.DataFrame()
        try:
            with get_db() as conn:
                log = pd.read_sql_query(
                    """SELECT date, sector_id, supplier, fuel_type,
                              quantity_liters, price_per_liter
                       FROM fuel_purchases
                       ORDER BY date DESC LIMIT 50""",
                    conn,
                )
        except Exception as e:
            logging.error(f"Error in fuel purchase log query: {e}")

        return {
            "buy_signal": signal_result,
            "weekly_budget": budget_result,
            "forecast": forecast_result,
            "purchase_log": _df(log),
        }
    except Exception:
        return {
            "buy_signal": {},
            "weekly_budget": {},
            "forecast": {},
            "purchase_log": [],
        }


# ---------- 8. Yesterday Comparison ----------

@router.get("/yesterday-comparison")
def yesterday_comparison(site_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    try:
        metrics = []
        type_filter = ""
        type_params = []
        type_join = ""
        if site_type and site_type != 'All':
            type_join = " JOIN sites s ON dss.site_id = s.site_id"
            type_filter = " AND s.site_type = ?"
            type_params = [site_type]

        with get_db() as conn:
            # Use daily_site_summary for consistency with all other endpoints
            yesterday = pd.read_sql_query(f"""
                SELECT
                       SUM(dss.total_daily_used) AS burn,
                       SUM(dss.spare_tank_balance) AS tank,
                       SUM(dss.blackout_hr) AS blackout_hr
                   FROM daily_site_summary dss{type_join}
                   WHERE dss.date = (SELECT MAX(date) FROM daily_site_summary){type_filter}""",
                conn, params=type_params,
            )

            # 3-day avg (prior 3 days, excluding latest)
            avg_3d = pd.read_sql_query(f"""
                SELECT
                       SUM(dss.total_daily_used) / COUNT(DISTINCT dss.date) AS burn,
                       SUM(dss.blackout_hr) / COUNT(DISTINCT dss.date) AS blackout_hr
                   FROM daily_site_summary dss{type_join}
                   WHERE dss.date >= (SELECT date(MAX(date), '-3 days') FROM daily_site_summary)
                     AND dss.date < (SELECT MAX(date) FROM daily_site_summary){type_filter}""",
                conn, params=type_params,
            )

            # Buffer: last_day_tank / 3d_avg_fuel
            y_tank = float(yesterday["tank"].iloc[0] or 0) if not yesterday.empty else 0
            y_burn = float(yesterday["burn"].iloc[0] or 0) if not yesterday.empty else 0
            a_burn = float(avg_3d["burn"].iloc[0] or 0) if not avg_3d.empty else 0
            y_buffer = y_tank / a_burn if a_burn > 0 else (y_tank / y_burn if y_burn > 0 else 0)

            # Cost via date-specific price lookup
            max_date_row = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()
            max_date = max_date_row[0] if max_date_row else None
            y_cost = 0
            a_cost = 0
            if max_date:
                # Per-sector cost for yesterday
                sector_fuels = pd.read_sql_query(f"""
                    SELECT s.sector_id, SUM(dss.total_daily_used) as fuel
                    FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id
                    WHERE dss.date = ?{type_filter} GROUP BY s.sector_id
                """, conn, params=[max_date] + type_params)
                for _, r in sector_fuels.iterrows():
                    from backend.routers.data import _sector_price_on_date
                    p = _sector_price_on_date(conn, r["sector_id"], max_date)
                    y_cost += (r["fuel"] or 0) * p

                # Per-sector cost for 3d avg
                sector_fuels_3d = pd.read_sql_query(f"""
                    SELECT s.sector_id,
                           SUM(dss.total_daily_used) / COUNT(DISTINCT dss.date) as fuel
                    FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id
                    WHERE dss.date >= date(?, '-3 days') AND dss.date < ?{type_filter}
                    GROUP BY s.sector_id
                """, conn, params=[max_date, max_date] + type_params)
                for _, r in sector_fuels_3d.iterrows():
                    p = _sector_price_on_date(conn, r["sector_id"], max_date)
                    a_cost += (r["fuel"] or 0) * p

            # 3d buffer: use last_day_tank / 3d_avg_burn (same formula)
            a_buffer = y_tank / a_burn if a_burn > 0 else 0
            # Override yesterday values
            yesterday = pd.DataFrame([{
                "burn": y_burn, "buffer": y_buffer,
                "cost": y_cost, "blackout_hr": float(yesterday["blackout_hr"].iloc[0] or 0) if not yesterday.empty else 0
            }])
            avg_3d = pd.DataFrame([{
                "burn": a_burn, "buffer": a_buffer,
                "cost": a_cost, "blackout_hr": float(avg_3d["blackout_hr"].iloc[0] or 0) if not avg_3d.empty else 0
            }])

        for col, label in [("burn", "BURN"), ("buffer", "BUFFER"),
                           ("cost", "COST"), ("blackout_hr", "BLACKOUT_HR")]:
            y_val = float(yesterday[col].iloc[0] or 0) if not yesterday.empty else 0
            a_val = float(avg_3d[col].iloc[0] or 0) if not avg_3d.empty else 0
            if a_val:
                pct = round((y_val - a_val) / a_val * 100, 1)
            else:
                pct = 0.0
            direction = "up" if pct > 1 else "down" if pct < -1 else "flat"
            metrics.append({
                "name": label,
                "yesterday": round(y_val, 1),
                "avg_3d": round(a_val, 1),
                "pct_change": pct,
                "direction": direction,
            })

        return {"metrics": metrics}
    except Exception:
        return {"metrics": []}


# ---------- 8b. Period KPIs (Last Day + Last 3 Days) ----------

@router.get("/period-kpis")
def period_kpis(sector: Optional[str] = None, date_to: Optional[str] = None, site_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Return full KPI blocks for last day and last 3 days avg.
    If date_to is provided, use it as the latest date (from calendar filter).
    """
    try:
        with get_db() as conn:
            # Build parameterized filter clauses
            filter_clauses = []
            filter_params = []
            if sector:
                filter_clauses.append("AND s.sector_id = ?")
                filter_params.append(sector)
            if site_type and site_type != 'All':
                filter_clauses.append("AND s.site_type = ?")
                filter_params.append(site_type)
            sector_sql = " ".join(filter_clauses)
            if date_to:
                # Use the provided end date, but find the actual max date <= date_to
                _row = conn.execute(
                    f"SELECT MAX(dss.date) FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id WHERE dss.date <= ? {sector_sql}",
                    [date_to] + filter_params
                ).fetchone()
                max_date = _row[0] if _row else None
            else:
                _row = conn.execute(
                    f"SELECT MAX(dss.date) FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id WHERE 1=1 {sector_sql}",
                    filter_params
                ).fetchone()
                max_date = _row[0] if _row else None
            if not max_date:
                return {"last_day": None, "last_3d": None, "max_date": None}

            def _build_kpis(date_filter, label, date_params=None):
                query_params = (date_params or []) + filter_params
                df = pd.read_sql_query(f"""
                    SELECT dss.site_id, s.sector_id, dss.date,
                           dss.total_daily_used, dss.spare_tank_balance, dss.days_of_buffer,
                           dss.total_gen_run_hr, dss.blackout_hr
                    FROM daily_site_summary dss
                    JOIN sites s ON dss.site_id = s.site_id
                    WHERE {date_filter} {sector_sql}
                """, conn, params=query_params)
                if df.empty:
                    return None
                n_days = df["date"].nunique()
                n_sites = df["site_id"].nunique()
                # Generator count for these sites
                site_ids = df["site_id"].unique().tolist()
                if site_ids:
                    placeholders = ','.join(['?' for _ in site_ids])
                    row = conn.execute(f"SELECT COUNT(*) FROM generators WHERE is_active=1 AND site_id IN ({placeholders})", site_ids).fetchone()
                    n_gens = row[0] if row else 0
                else:
                    n_gens = 0
                # Daily totals per date (for proper averaging)
                daily_totals = df.groupby("date").agg(
                    daily_tank=("spare_tank_balance", lambda x: x.fillna(0).sum()),
                    daily_fuel=("total_daily_used", lambda x: x.fillna(0).sum()),
                    daily_gen_hr=("total_gen_run_hr", lambda x: x.fillna(0).sum()),
                    daily_blackout=("blackout_hr", lambda x: x.fillna(0).sum()),
                ).reset_index()

                # Tank: always use latest day's SUM (current stock level)
                daily_totals_sorted = daily_totals.sort_values("date")
                tank = float(daily_totals_sorted["daily_tank"].iloc[-1])  # last day's tank
                total_fuel = float(daily_totals["daily_fuel"].sum())
                burn = total_fuel / max(n_days, 1)
                # Buffer: always last_day_tank / 3d_avg_fuel (standardized formula)
                # Get 3-day avg fuel from prior 3 days for buffer calculation
                avg3d_fuel_row = conn.execute(f"""
                    SELECT SUM(dss.total_daily_used) / COUNT(DISTINCT dss.date) as avg_fuel
                    FROM daily_site_summary dss
                    JOIN sites s ON dss.site_id = s.site_id
                    WHERE dss.date >= date(?, '-3 days') AND dss.date < ? {sector_sql}
                """, [max_date, max_date] + filter_params).fetchone()
                avg3d_fuel = avg3d_fuel_row[0] if avg3d_fuel_row and avg3d_fuel_row[0] else burn
                buffer = tank / avg3d_fuel if avg3d_fuel > 0 else 0
                total_gen_hr = float(daily_totals["daily_gen_hr"].sum())
                gen_hr = total_gen_hr / max(n_days, 1)
                total_blackout = float(daily_totals["daily_blackout"].sum())
                latest = df.sort_values("date").groupby("site_id").last()
                crit = int((latest["days_of_buffer"] < 3).sum())
                warn = int(((latest["days_of_buffer"] >= 3) & (latest["days_of_buffer"] < 7)).sum())
                safe = int((latest["days_of_buffer"] >= 7).sum())
                no_data = n_sites - crit - warn - safe
                needed = latest[latest["days_of_buffer"] < 7].apply(
                    lambda r: max(0, 7 * (r["total_daily_used"] or 0) - (r["spare_tank_balance"] or 0)), axis=1
                ).sum() if not latest.empty else 0
                # Get fuel price — date-specific: latest purchase price on or before max_date
                if sector:
                    price_row = conn.execute("""
                        SELECT price_per_liter FROM fuel_purchases
                        WHERE sector_id = ? AND date <= ? AND price_per_liter IS NOT NULL
                        ORDER BY date DESC LIMIT 1
                    """, (sector, max_date)).fetchone()
                    price = price_row[0] if price_row else 0
                else:
                    # Group view: weighted avg of latest sector prices
                    price_rows = conn.execute("""
                        SELECT sector_id, price_per_liter FROM fuel_purchases
                        WHERE price_per_liter IS NOT NULL
                        GROUP BY sector_id HAVING date = MAX(date)
                    """).fetchall()
                    if price_rows:
                        prices_list = [r["price_per_liter"] for r in price_rows]
                        price = sum(prices_list) / len(prices_list)
                    else:
                        price = 0
                cost = burn * price
                # Sales — use latest available sales date if no sales on ops date
                sales_date_filter = date_filter.replace('dss.','').replace('s.','')
                sales_q = f"SELECT COALESCE(SUM(sales_amt),0) FROM daily_sales WHERE {sales_date_filter}"
                sector_sales_filter = " AND sector_id = ?" if sector else ""
                sector_sales_params = list(date_params or [])
                if sector:
                    sector_sales_params.append(sector)
                try:
                    _row = conn.execute(sales_q + sector_sales_filter, sector_sales_params).fetchone()
                    sales = (_row[0] if _row else 0) / max(n_days, 1)
                except Exception:
                    sales = 0
                # Fallback: if no sales on exact date, try latest available sales date
                if sales == 0:
                    try:
                        _row = conn.execute(
                            f"SELECT MAX(date) FROM daily_sales WHERE sales_amt > 0{sector_sales_filter}",
                            sector_sales_params
                        ).fetchone()
                        max_sales_date = _row[0] if _row else None
                        if max_sales_date:
                            _row = conn.execute(
                                f"SELECT COALESCE(SUM(sales_amt),0) FROM daily_sales WHERE date = ?{sector_sales_filter}",
                                [max_sales_date] + sector_sales_params
                            ).fetchone()
                            fallback_sales = _row[0] if _row else 0
                            if fallback_sales > 0:
                                sales = fallback_sales
                    except Exception as e:
                        logging.error(f"Error in fallback sales query: {e}")
                diesel_pct = (cost / sales * 100) if sales > 0 else 0
                # Blackout per site per day (SUM-based: total_blackout / sites / days)
                blackout = total_blackout / max(n_sites, 1) / max(n_days, 1) if total_blackout > 0 else 0
                # Critical sites list (for cockpit)
                crit_sites = []
                if not latest.empty:
                    crit_df = latest[latest["days_of_buffer"] < 3].sort_values("days_of_buffer")
                    for sid, r in crit_df.iterrows():
                        crit_sites.append({
                            "site_id": sid, "buffer": round(r["days_of_buffer"], 1),
                            "tank": round(r["spare_tank_balance"] or 0),
                            "burn": round(r["total_daily_used"] or 0),
                            "needed": round(max(0, 7 * (r["total_daily_used"] or 0) - (r["spare_tank_balance"] or 0))),
                        })
                # Efficiency
                efficiency = float(burn / gen_hr) if gen_hr > 0 else 0
                if pd.isna(efficiency): efficiency = 0
                # Total sites in system (for data quality)
                total_sites_q = f"SELECT COUNT(*) FROM sites s WHERE 1=1 {sector_sql}"
                _row = conn.execute(total_sites_q, filter_params).fetchone()
                total_sites_in_system = _row[0] if _row else 0
                sites_not_reported = total_sites_in_system - n_sites
                # Sites with missing tank
                tank_missing = int((latest["spare_tank_balance"].fillna(0) == 0).sum()) if not latest.empty else 0

                tank_per_site = round(tank / n_sites, 1) if n_sites > 0 else 0
                fuel_per_site = round(burn / n_sites, 1) if n_sites > 0 else 0
                blackout_per_site = round(total_blackout / n_sites / max(n_days, 1), 1) if n_sites > 0 else 0
                gen_hr_per_site = gen_hr / n_sites if n_sites > 0 else 0

                return {
                    "label": label, "date": max_date, "sites": n_sites, "days": n_days,
                    "generators": n_gens, "total_sites": total_sites_in_system,
                    "buffer": round(buffer, 1), "tank": round(tank), "burn": round(burn),
                    "needed": round(needed), "cost": round(cost), "gen_hr": round(gen_hr),
                    "total_gen_hr": round(total_gen_hr, 1),
                    "gen_hr_per_site": round(gen_hr_per_site, 1),
                    "total_fuel": round(total_fuel),
                    "fuel_per_site": round(fuel_per_site, 1),
                    "tank_per_site": round(tank_per_site),
                    "total_blackout": round(total_blackout, 1),
                    "blackout": round(blackout, 1) if blackout else 0,
                    "blackout_per_site": round(blackout_per_site, 1),
                    "efficiency": round(efficiency, 1),
                    "fuel_price": round(price),
                    "stock_value": round(tank * price),
                    "crit": crit, "warn": warn, "safe": safe, "no_data": max(no_data, 0),
                    "sales": round(sales), "diesel_pct": round(diesel_pct, 2),
                    "has_sales": sales > 0,
                    "critical_sites": crit_sites[:10],
                    "sites_not_reported": sites_not_reported,
                    "tank_missing": tank_missing,
                }

            last_day = _build_kpis("dss.date = ?", "LATEST_DATA", [max_date])
            last_3d = _build_kpis("dss.date >= date(?, '-3 days') AND dss.date < ?", "PRIOR_3_DAYS_AVG", [max_date, max_date])

            # Sector snapshot (for group view)
            sector_snapshot = []
            if not sector:
                try:
                    for sec_row in conn.execute("SELECT sector_id, sector_name FROM sectors ORDER BY sector_id").fetchall():
                        sid = sec_row[0]
                        sec_data = pd.read_sql_query("""
                            SELECT dss.site_id, dss.total_daily_used, dss.spare_tank_balance, dss.days_of_buffer, dss.blackout_hr
                            FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id
                            WHERE dss.date = ? AND s.sector_id = ?
                        """, conn, params=[max_date, sid])
                        if sec_data.empty:
                            continue
                        s_tank = sec_data["spare_tank_balance"].fillna(0).sum()
                        s_burn = sec_data["total_daily_used"].fillna(0).sum()
                        s_buf = s_tank / s_burn if s_burn > 0 else 0
                        s_crit = int((sec_data["days_of_buffer"].fillna(0) < 3).sum())
                        s_bo = sec_data["blackout_hr"].fillna(0).sum() / max(len(sec_data), 1)
                        # Get price for sector
                        s_price_row = conn.execute("SELECT price_per_liter FROM fuel_purchases WHERE sector_id=? AND price_per_liter IS NOT NULL ORDER BY date DESC LIMIT 1", [sid]).fetchone()
                        s_price = s_price_row[0] if s_price_row else 0
                        s_cost = s_burn * s_price
                        # Sales
                        s_sales_row = conn.execute("SELECT COALESCE(SUM(sales_amt),0) FROM daily_sales WHERE date=? AND sector_id=?", [max_date, sid]).fetchone()
                        s_sales = s_sales_row[0] if s_sales_row else 0
                        s_dpct = (s_cost / s_sales * 100) if s_sales > 0 else -1
                        status = "🟢" if s_buf >= 7 else "🟡" if s_buf >= 3 else "🔴" if s_burn > 0 else "⚪"
                        # Generator counts: total and running on latest date
                        site_ids = sec_data["site_id"].unique().tolist()
                        total_gens = 0
                        running_gens = 0
                        if site_ids:
                            ph = ','.join(['?' for _ in site_ids])
                            row_tg = conn.execute(f"SELECT COUNT(*) FROM generators WHERE is_active=1 AND site_id IN ({ph})", site_ids).fetchone()
                            total_gens = row_tg[0] if row_tg else 0
                            row_rg = conn.execute(f"""
                                SELECT COUNT(DISTINCT do.generator_id)
                                FROM daily_operations do
                                WHERE do.date = ? AND do.gen_run_hr > 0
                                  AND do.site_id IN ({ph})
                            """, [max_date] + site_ids).fetchone()
                            running_gens = row_rg[0] if row_rg else 0
                        sector_snapshot.append({
                            "sector": sid, "sites": len(sec_data), "buffer": round(s_buf, 1),
                            "burn": round(s_burn), "cost": round(s_cost), "blackout": round(s_bo or 0, 1),
                            "diesel_pct": round(s_dpct, 2) if s_dpct >= 0 else None,
                            "crit": s_crit, "status": status,
                            "total_gens": total_gens, "running_gens": running_gens,
                        })
                except Exception as e:
                    logging.error(f"Error in sector snapshot aggregation: {e}")

            # Operating mode counts
            op_modes = {"OPEN": 0, "MONITOR": 0, "REDUCE": 0, "CLOSE": 0}
            try:
                from models.decision_engine import get_operating_modes
                modes_df = get_operating_modes()
                if modes_df is not None and not modes_df.empty:
                    if sector:
                        modes_df = modes_df[modes_df.get("sector_id", pd.Series()) == sector] if "sector_id" in modes_df.columns else modes_df
                    for m in ["OPEN", "MONITOR", "REDUCE", "CLOSE"]:
                        col = "operating_mode" if "operating_mode" in modes_df.columns else "mode"
                        if col in modes_df.columns:
                            op_modes[m] = int((modes_df[col].str.upper() == m).sum())
            except Exception as e:
                logging.error(f"Error in operating modes import: {e}")

            # Recent daily totals for sparklines (4 days: 3 prior + latest)
            recent_daily = []
            try:
                rdf = pd.read_sql_query(f"""
                    SELECT dss.date,
                        SUM(dss.total_gen_run_hr) as gen_hr,
                        SUM(dss.total_daily_used) as fuel,
                        SUM(dss.spare_tank_balance) as tank,
                        SUM(dss.blackout_hr) as blackout,
                        COUNT(DISTINCT dss.site_id) as sites
                    FROM daily_site_summary dss
                    JOIN sites s ON dss.site_id = s.site_id
                    WHERE dss.date >= date(?, '-3 days') {sector_sql}
                    GROUP BY dss.date ORDER BY dss.date
                """, conn, params=[max_date] + filter_params)
                # Get sales per date
                sales_by_date = {}
                try:
                    sales_sql = "SELECT date, SUM(sales_amt) as sales FROM daily_sales WHERE date >= date(?, '-3 days')"
                    sales_params = [max_date]
                    if sector:
                        sales_sql += " AND sector_id = ?"
                        sales_params.append(sector)
                    sales_sql += " GROUP BY date"
                    sdf = pd.read_sql_query(sales_sql, conn, params=sales_params)
                    for _, sr in sdf.iterrows():
                        sales_by_date[sr["date"]] = float(sr["sales"] or 0)
                except Exception as e:
                    logging.error(f"Error in sales by date query: {e}")
                # Get sector prices for cost calculation
                sector_prices = {}
                for pr in conn.execute("SELECT sector_id, price_per_liter FROM fuel_purchases WHERE price_per_liter IS NOT NULL GROUP BY sector_id HAVING date = MAX(date)").fetchall():
                    sector_prices[pr[0]] = pr[1]
                avg_price = sum(sector_prices.values()) / max(len(sector_prices), 1) if sector_prices else 0
                price = sector_prices.get(sector, avg_price) if sector else avg_price

                for _, r in rdf.iterrows():
                    b = r["fuel"]
                    t = r["tank"] or 0
                    dt = r["date"]
                    day_sales = sales_by_date.get(dt, 0)
                    day_cost = round((b or 0) * price)
                    day_dpct = round(day_cost / day_sales * 100, 2) if day_sales > 0 else 0
                    recent_daily.append({
                        "date": dt, "gen_hr": round(r["gen_hr"] or 0, 1),
                        "fuel": round(b or 0), "tank": round(t),
                        "blackout": round(r["blackout"] or 0, 1),
                        "buffer": round(t / b, 1) if b and b > 0 else 0,
                        "sites": int(r["sites"]),
                        "sales": round(day_sales), "cost": day_cost,
                        "diesel_pct": day_dpct,
                        "stock_value": round(t * price),
                    })
            except Exception as e:
                logging.error(f"Error in recent daily aggregation: {e}")

            # Story line — auto-generated narrative
            story = []
            if last_day:
                ld = last_day
                story.append(f"On {max_date}, {ld['sites']} sites reported with {fmtN(ld['tank'])}L fuel remaining ({ld['buffer']}d buffer).")
                if last_3d:
                    t3 = last_3d
                    bd = ld['buffer'] - t3['buffer']
                    if bd < -1:
                        story.append(f"Buffer dropped {abs(bd):.1f} days vs prior 3-day average — fuel is depleting faster than resupply.")
                    elif bd > 1:
                        story.append(f"Buffer improved by {bd:.1f} days vs prior 3 days — resupply is outpacing consumption.")
                    else:
                        story.append("Buffer is stable compared to prior 3 days.")
                if ld.get('crit', 0) > 0:
                    story.append(f"{ld['crit']} sites are CRITICAL (<3 days fuel) and need immediate delivery of {fmtN(ld.get('needed',0))}L.")
                if (ld.get('sites_not_reported', 0)) > 0:
                    story.append(f"{ld['sites_not_reported']} sites did not report — data may be incomplete.")
                gen_hr = ld.get('total_gen_hr', 0)
                if gen_hr > 0:
                    story.append(f"Generators ran {fmtN(gen_hr)} hours total, consuming {fmtN(ld.get('total_fuel', ld.get('burn',0)))}L of diesel at {fmtN(ld.get('efficiency',0))} L/Hr efficiency.")

        return _sanitize({
            "last_day": last_day, "last_3d": last_3d, "max_date": max_date,
            "sector_snapshot": sector_snapshot,
            "operating_modes": op_modes,
            "recent_daily": recent_daily,
            "story": story,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"last_day": None, "last_3d": None, "max_date": None}


# ---------- 9. Generator Risk ----------

@router.get("/generator-risk")
def generator_risk(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_generator_failure_risk
        result = get_generator_failure_risk()
        return {"generators": _df(_enrich_site_code(result))}
    except Exception:
        return {"generators": []}


# ---------- 10. Site Mapping ----------

@router.get("/site-mapping")
def site_mapping(user: dict = Depends(get_current_user)):
    try:
        with get_db() as conn:
            mapped = pd.read_sql_query("""
                SELECT DISTINCT s.site_id, s.sector_id, s.site_name, s.cost_center_code,
                       s.region as site_code, s.segment_name, s.cost_center_description,
                       s.address_state, s.store_size, s.latitude, s.longitude,
                       COUNT(DISTINCT ds.date) as sales_days, SUM(ds.sales_amt) as total_sales
                FROM sites s
                JOIN daily_sales ds ON ds.site_id = s.site_id
                GROUP BY s.site_id ORDER BY s.sector_id, s.site_id
            """, conn)
            unmapped = pd.read_sql_query("""
                SELECT s.site_id, s.sector_id, s.site_name, s.cost_center_code,
                       s.region as site_code, s.segment_name, s.cost_center_description,
                       s.address_state, s.store_size, s.latitude, s.longitude
                FROM sites s
                WHERE s.site_id NOT IN (SELECT DISTINCT site_id FROM daily_sales WHERE site_id IS NOT NULL)
                ORDER BY s.sector_id, s.site_id
            """, conn)
        return {"mapped": _df(mapped), "unmapped": _df(unmapped), "mapped_count": len(mapped), "unmapped_count": len(unmapped)}
    except Exception:
        return {"mapped": [], "unmapped": [], "mapped_count": 0, "unmapped_count": 0}


# ---------- 11. Transfers ----------

@router.get("/transfers")
def transfers(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_resource_sharing_opportunities, get_load_optimization
        transfers = get_resource_sharing_opportunities()
        load_opt = get_load_optimization()
        return {"transfers": transfers if isinstance(transfers, list) else _df(_enrich_site_code(transfers)), "load_optimization": _df(_enrich_site_code(load_opt))}
    except Exception:
        return {"transfers": [], "load_optimization": []}


# ---------- 12. Anomalies ----------

@router.get("/anomalies")
def anomalies(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_consumption_anomalies
        anomalies = get_consumption_anomalies()
        return {"anomalies": _df(anomalies)}
    except Exception:
        return {"anomalies": []}


# ---------- 13. Break-Even ----------

@router.get("/break-even")
def break_even(user: dict = Depends(get_current_user)):
    try:
        with get_db() as conn:
            df = pd.read_sql_query("""
                SELECT s.site_id, s.sector_id, s.cost_center_code,
                       s.region as site_code, s.segment_name, s.cost_center_description,
                       s.address_state, s.store_size, s.latitude, s.longitude,
                       COALESCE(AVG(dss.total_daily_used), 0) as avg_daily_fuel,
                       COALESCE(sales.avg_sales, 0) as avg_daily_sales
                FROM sites s
                LEFT JOIN daily_site_summary dss ON s.site_id = dss.site_id
                LEFT JOIN (
                    SELECT site_id, AVG(sales_amt) as avg_sales
                    FROM daily_sales WHERE site_id IS NOT NULL
                    GROUP BY site_id
                ) sales ON s.site_id = sales.site_id
                GROUP BY s.site_id
            """, conn)

            # Get latest fuel price per sector
            prices = {}
            for row in conn.execute("SELECT sector_id, price_per_liter FROM fuel_purchases WHERE price_per_liter IS NOT NULL ORDER BY date DESC").fetchall():
                if row[0] not in prices:
                    prices[row[0]] = row[1]

        if not df.empty:
            df["fuel_price"] = df["sector_id"].map(prices).fillna(0)
            df["daily_cost"] = df["avg_daily_fuel"] * df["fuel_price"]
            df["diesel_pct"] = np.where(df["avg_daily_sales"] > 0, df["daily_cost"] / df["avg_daily_sales"] * 100, 0)
            df["recommendation"] = df["diesel_pct"].apply(lambda x: "CLOSE" if x > 30 else "REDUCE" if x > 15 else "MONITOR" if x > 5 else "OPEN")
            df = df.sort_values("diesel_pct", ascending=False)

        return {"sites": _df(df.round(2))}
    except Exception:
        return {"sites": []}


# ---------- 14. Sector Sites ----------

@router.get("/sector-sites")
def sector_sites(sector: Optional[str] = None, site_type: Optional[str] = None, lookback: int = 3, user: dict = Depends(get_current_user)):
    """All sites with threshold indicators using N-day lookback for averages."""
    try:
        # Load formula settings
        import json
        with get_db() as conn:
            raw = conn.execute("SELECT value FROM app_settings WHERE key='formula_engine'").fetchone()
            if raw and raw[0]:
                try:
                    settings = json.loads(raw[0])
                    lookback = settings.get("lookback_days", lookback)
                except Exception as e:
                    logging.error(f"Error parsing formula_engine settings: {e}")

            sector_sql = "AND s.sector_id = ?" if sector else ""
            sector_params = [sector] if sector else []
            if site_type and site_type != 'All':
                sector_sql += " AND s.site_type = ?"
                sector_params.append(site_type)

            # Get last N days of data (for averages) + last day tank (for buffer)
            lookback_days_val = max(lookback-1, 0)
            df = pd.read_sql_query(f"""
                SELECT s.site_id, s.sector_id, s.site_name, s.site_type, s.company,
                       s.cost_center_code, s.region as site_code, s.segment_name,
                       s.cost_center_description, s.address_state, s.address_township,
                       s.store_size, s.channel, s.latitude, s.longitude,
                       avg_data.avg_fuel as daily_fuel,
                       avg_data.avg_tank as avg3d_tank,
                       last_data.spare_tank_balance as tank,
                       last_data.days_of_buffer as buffer_days,
                       last_data.total_daily_used as last_day_fuel,
                       last_data.blackout_hr as last_day_blackout,
                       avg_data.avg_gen_hr as gen_hr,
                       COALESCE(avg_data.avg_blackout, bo_all.avg_blackout_all) as blackout_hr,
                       avg_data.total_fuel,
                       avg_data.total_gen_hr,
                       avg_data.data_days
                FROM sites s
                LEFT JOIN (
                    SELECT site_id,
                           AVG(total_daily_used) as avg_fuel,
                           AVG(total_gen_run_hr) as avg_gen_hr,
                           AVG(CASE WHEN blackout_hr IS NOT NULL AND blackout_hr != '' THEN blackout_hr END) as avg_blackout,
                           AVG(spare_tank_balance) as avg_tank,
                           SUM(total_daily_used) as total_fuel,
                           SUM(total_gen_run_hr) as total_gen_hr,
                           COUNT(DISTINCT date) as data_days
                    FROM daily_site_summary
                    WHERE date >= (SELECT date(MAX(date), '-{lookback_days_val} days') FROM daily_site_summary)
                    GROUP BY site_id
                ) avg_data ON s.site_id = avg_data.site_id
                LEFT JOIN (
                    SELECT site_id,
                           AVG(CASE WHEN blackout_hr IS NOT NULL AND blackout_hr > 0 THEN blackout_hr END) as avg_blackout_all
                    FROM daily_site_summary
                    GROUP BY site_id
                ) bo_all ON s.site_id = bo_all.site_id
                LEFT JOIN (
                    SELECT site_id, spare_tank_balance, days_of_buffer, total_daily_used, blackout_hr
                    FROM daily_site_summary
                    WHERE date = (SELECT MAX(date) FROM daily_site_summary)
                ) last_data ON s.site_id = last_data.site_id
                WHERE 1=1 {sector_sql}
                AND s.cost_center_code NOT IN (SELECT store_cost_center FROM store_center_allocation)
                ORDER BY s.sector_id, s.site_id
            """, conn, params=sector_params)

            # Get fuel prices per sector
            prices = {}
            for row in conn.execute("SELECT sector_id, price_per_liter FROM fuel_purchases WHERE price_per_liter IS NOT NULL ORDER BY date DESC").fetchall():
                if row[0] not in prices:
                    prices[row[0]] = row[1]

            # Get sales per site — total period
            sales = pd.read_sql_query("""
                SELECT site_id, SUM(sales_amt) as total_sales,
                       SUM(sales_amt) / COUNT(DISTINCT date) as daily_sales,
                       SUM(margin) as total_margin,
                       SUM(margin) / NULLIF(SUM(sales_amt), 0) * 100 as margin_pct_calc
                FROM daily_sales WHERE site_id IS NOT NULL
                GROUP BY site_id
            """, conn)

            # Get last day sales per site
            _row = conn.execute("SELECT MAX(date) FROM daily_sales WHERE site_id IS NOT NULL").fetchone()
            max_sales_date = _row[0] if _row else None
            last_day_sales = pd.DataFrame()
            avg3d_sales = pd.DataFrame()
            if max_sales_date:
                last_day_sales = pd.read_sql_query("""
                    SELECT site_id, sales_amt as last_day_sales, margin as last_day_margin
                    FROM daily_sales WHERE date = ? AND site_id IS NOT NULL
                """, conn, params=[max_sales_date])
                # 3D avg sales (3 days before last sales date)
                avg3d_sales = pd.read_sql_query("""
                    SELECT site_id,
                           AVG(sales_amt) as avg3d_sales,
                           AVG(margin) as avg3d_margin
                    FROM daily_sales
                    WHERE date >= date(?, '-3 days') AND date < ?
                      AND site_id IS NOT NULL
                    GROUP BY site_id
                """, conn, params=[max_sales_date, max_sales_date])

            # Get LY expense per site
            ly = pd.read_sql_query("SELECT cost_center_code, pct_on_sales FROM diesel_expense_ly", conn)

            # Get LY baseline data (daily_avg_expense and pct_on_sales)
            ly_data = {}
            ly_rows = conn.execute("""
                SELECT cost_center_code, daily_avg_expense_mmk, pct_on_sales
                FROM diesel_expense_ly
            """).fetchall()
            for r in ly_rows:
                ly_data[r[0]] = {"ly_daily_cost": r[1] or 0, "ly_pct_on_sales": (r[2] or 0) * 100}

            # Load thresholds from settings
            thresholds = {"exp_open": 5, "exp_monitor": 15, "exp_reduce": 30, "exp_close": 60}
            if raw and raw[0]:
                try:
                    thresholds.update(json.loads(raw[0]).get("thresholds", {}))
                except Exception as e:
                    logging.error(f"Error parsing threshold settings: {e}")

            if not df.empty:
                df["price"] = df["sector_id"].map(prices).fillna(0)
                # Buffer = last day tank ÷ avg daily burn (N-day lookback)
                df["buffer_days"] = np.where(df["daily_fuel"].fillna(0) > 0,
                    df["tank"].fillna(0) / df["daily_fuel"], 0)
                df["daily_cost"] = (df["daily_fuel"].fillna(0) * df["price"]).round(0)
                df["total_cost"] = (df["total_fuel"].fillna(0) * df["price"]).round(0)

                if not sales.empty:
                    df = df.merge(sales, on="site_id", how="left")
                else:
                    df["total_sales"] = 0; df["daily_sales"] = 0; df["total_margin"] = 0

                if not last_day_sales.empty:
                    df = df.merge(last_day_sales, on="site_id", how="left")
                else:
                    df["last_day_sales"] = 0; df["last_day_margin"] = 0

                if not avg3d_sales.empty:
                    df = df.merge(avg3d_sales, on="site_id", how="left")
                else:
                    df["avg3d_sales"] = 0; df["avg3d_margin"] = 0

                # Last day fuel cost (actual last day fuel × price)
                df["last_day_fuel_cost"] = df["last_day_fuel"].fillna(0) * df["price"]
                # Avg 3D fuel cost (3d avg fuel × price)
                df["avg3d_fuel_cost"] = df["daily_fuel"].fillna(0) * df["price"]

                # Exp% calculations
                df["exp_pct"] = np.where(df["daily_sales"].fillna(0) > 0,
                    df["daily_cost"] / df["daily_sales"] * 100, 0)
                df["exp_pct_last_day"] = np.where(df["last_day_sales"].fillna(0) > 0,
                    df["last_day_fuel_cost"] / df["last_day_sales"] * 100, 0)
                df["exp_pct_3d"] = np.where(df["avg3d_sales"].fillna(0) > 0,
                    df["avg3d_fuel_cost"] / df["avg3d_sales"] * 100, 0)
                df["exp_pct_total"] = np.where(df["total_sales"].fillna(0) > 0,
                    (df["total_fuel"].fillna(0) * df["price"]) / df["total_sales"] * 100, 0)

                # Margin
                df["margin_pct"] = np.where(df["total_sales"].fillna(0) > 0,
                    df["total_margin"].fillna(0) / df["total_sales"] * 100, 0)
                df["margin_pct_last_day"] = np.where(df["last_day_sales"].fillna(0) > 0,
                    df["last_day_margin"].fillna(0) / df["last_day_sales"] * 100, 0)
                df["margin_pct_3d"] = np.where(df["avg3d_sales"].fillna(0) > 0,
                    df["avg3d_margin"].fillna(0) / df["avg3d_sales"] * 100, 0)

                # Operating mode using configurable thresholds
                t = thresholds
                df["action"] = df["exp_pct"].apply(
                    lambda x: "CLOSE" if x > t.get("exp_close", 60) else "REDUCE" if x > t.get("exp_reduce", 30) else "MONITOR" if x > t.get("exp_monitor", 15) else "OPEN"
                )

                # Add LY baseline columns
                df["ly_daily_cost"] = df["cost_center_code"].map(
                    lambda cc: round(ly_data.get(str(cc), {}).get("ly_daily_cost", 0), 0)
                )
                df["ly_pct_on_sales"] = df["cost_center_code"].map(
                    lambda cc: round(ly_data.get(str(cc), {}).get("ly_pct_on_sales", 0), 2)
                )

                df = df.fillna(0).round(2)

            # Sector-level 3d avg fuel for correct summary buffer (matches heatmap formula)
            sector_3d_avg_fuel = {}
            try:
                _row = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()
                max_dt = _row[0] if _row else None
                if max_dt:
                    s3d = pd.read_sql_query("""
                        SELECT s.sector_id,
                               SUM(dss.total_daily_used) / COUNT(DISTINCT dss.date) as avg_fuel_3d
                        FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id
                        WHERE dss.date >= date(?, '-3 days') AND dss.date < ?
                        GROUP BY s.sector_id
                    """, conn, params=[max_dt, max_dt])
                    for _, r in s3d.iterrows():
                        sector_3d_avg_fuel[r["sector_id"]] = round(r["avg_fuel_3d"], 1)
            except Exception as e:
                logging.error(f"Error in sector 3d avg fuel query: {e}")

        return {"sites": _df(df), "count": len(df), "sector_3d_avg_fuel": sector_3d_avg_fuel}
    except Exception as e:
        return {"sites": [], "count": 0}


# ---------- 16. Monthly Summary ----------

@router.get("/monthly-summary")
def monthly_summary(
    sector: Optional[str] = None,
    site_type: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    try:
        with get_db() as conn:
            site_conditions = []
            sp = []
            if sector:
                site_conditions.append("sector_id = ?")
                sp.append(sector)
            if site_type and site_type != 'All':
                site_conditions.append("site_type = ?")
                sp.append(site_type)
            sq = (" AND site_id IN (SELECT site_id FROM sites WHERE " + " AND ".join(site_conditions) + ")") if site_conditions else ""
            months = pd.read_sql_query(f"""
                SELECT strftime('%Y-%m', date) as month,
                       SUM(total_daily_used) as fuel, COUNT(DISTINCT date) as days,
                       COUNT(DISTINCT site_id) as sites,
                       SUM(spare_tank_balance) as tank,
                       SUM(CASE WHEN days_of_buffer < 3 THEN 1 ELSE 0 END) as crit_days
                FROM daily_site_summary WHERE 1=1{sq}
                GROUP BY month ORDER BY month DESC LIMIT 6
            """, conn, params=sp)

            bo = pd.read_sql_query(f"""
                SELECT strftime('%Y-%m', do.date) as month, AVG(do.blackout_hr) as avg_bo
                FROM daily_operations do
                WHERE do.blackout_hr IS NOT NULL{sq.replace('site_id', 'do.site_id')}
                GROUP BY month
            """, conn, params=sp)

        if months.empty:
            return []

        bo_map = dict(zip(bo["month"], bo["avg_bo"])) if not bo.empty else {}
        result = []
        for _, r in months.iterrows():
            m = r["month"]
            fuel = float(r["fuel"] or 0)
            days = int(r["days"] or 1)
            burn = fuel / days
            tank = float(r["tank"] or 0)
            buf = round(tank / max(burn, 1), 1)
            grade = "A" if buf > 10 else "B" if buf > 7 else "C" if buf > 5 else "D" if buf > 3 else "F"
            result.append({
                "month": m, "fuel": round(fuel), "days": days, "sites": int(r["sites"] or 0),
                "burn_per_day": round(burn), "blackout_hr": round(bo_map.get(m, 0), 1),
                "buffer": buf, "crit_days": int(r["crit_days"] or 0), "grade": grade,
            })
        return result
    except Exception:
        return []


# ---------- 17. Blackout Calendar ----------

@router.get("/blackout-calendar")
def blackout_calendar(
    sector: Optional[str] = None,
    site_type: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    try:
        with get_db() as conn:
            bo_conditions = []
            sp = []
            if sector:
                bo_conditions.append("sector_id = ?")
                sp.append(sector)
            if site_type and site_type != 'All':
                bo_conditions.append("site_type = ?")
                sp.append(site_type)
            sq = (" AND do.site_id IN (SELECT site_id FROM sites WHERE " + " AND ".join(bo_conditions) + ")") if bo_conditions else ""
            df = pd.read_sql_query(f"""
                SELECT do.date, AVG(do.blackout_hr) as avg_bo
                FROM daily_operations do
                WHERE do.blackout_hr IS NOT NULL{sq}
                GROUP BY do.date ORDER BY do.date
            """, conn, params=sp)

        if df.empty:
            return {"days": []}

        return {"days": [{"date": r["date"], "avg_bo": round(float(r["avg_bo"]), 1)} for _, r in df.iterrows()]}
    except Exception:
        return {"days": []}


# ---------- 18. Ocean Cost Allocation ----------

@router.get("/ocean-cost-allocation")
def ocean_cost_allocation(user: dict = Depends(get_current_user)):
    """Calculate Ocean store diesel costs using Center data × Store Contribution %.
    Stand Alone: 100% from own data.
    Shopping Center: % of CP center's diesel cost."""
    try:
        import os
        from pathlib import Path

        with get_db() as conn:
            # Load Store Exp % file
            exp_path = None
            for p in [Path("Data/Store Exp Percentage of Center.xlsx"), Path("data/Store Exp Percentage of Center.xlsx")]:
                if p.exists():
                    exp_path = p; break
            if not exp_path:
                # Try parent dirs
                for p in [Path(__file__).parent.parent.parent / "Data" / "Store Exp Percentage of Center.xlsx"]:
                    if p.exists():
                        exp_path = p; break

            store_exp_map = {}
            if exp_path and exp_path.exists():
                se = pd.read_excel(str(exp_path), sheet_name='Sheet1')
                for _, r in se.iterrows():
                    scc = str(int(r["Store's Cost Center Code"])) if pd.notna(r["Store's Cost Center Code"]) and isinstance(r["Store's Cost Center Code"], (int,float)) else ''
                    ccc = str(int(r["Center's Cost Center Code"])) if pd.notna(r["Center's Cost Center Code"]) and isinstance(r["Center's Cost Center Code"], (int,float)) else ''
                    pct = r.get("Store Contribution  (%) to Center Expense", 1)
                    remark = r.get("Remark", "")
                    ccn = r.get("Center's Cost Center Name", "")
                    if scc:
                        store_exp_map[scc] = {"center_cc": ccc, "pct": pct if pd.notna(pct) else 1, "type": str(remark) if pd.notna(remark) else "", "center_name": str(ccn) if pd.notna(ccn) else ""}

            # Get Ocean sites
            ocean_sites = pd.read_sql_query("SELECT site_id, site_name, region as site_code FROM sites WHERE segment_name = 'Ocean'", conn)

            # Get fuel prices
            cmhl_price = 0
            r = conn.execute("SELECT price_per_liter FROM fuel_purchases WHERE sector_id='CMHL' AND price_per_liter>0 ORDER BY date DESC LIMIT 1").fetchone()
            if r: cmhl_price = r[0]
            cp_price = 0
            r = conn.execute("SELECT price_per_liter FROM fuel_purchases WHERE sector_id='CP' AND price_per_liter>0 ORDER BY date DESC LIMIT 1").fetchone()
            if r: cp_price = r[0]

            results = []
            for _, oc in ocean_sites.iterrows():
                oid = oc['site_id']
                exp = store_exp_map.get(oid, {})
                center_cc = exp.get("center_cc", "")
                pct = exp.get("pct", 1)
                etype = exp.get("type", "Stand Alone")
                center_name = exp.get("center_name", "")

                if not center_cc or pct >= 1 or etype == "Stand Alone":
                    # Stand alone — use own data
                    own = conn.execute("SELECT COALESCE(SUM(total_daily_used),0), COUNT(DISTINCT date) FROM daily_site_summary WHERE site_id=?", (oid,)).fetchone()
                    fuel = own[0] if own else 0
                    days = own[1] if own else 0
                    cost = fuel * cmhl_price
                    results.append({
                        "ocean_site": oid, "ocean_name": oc['site_name'], "site_code": oc.get('site_code',''),
                        "center_cc": oid, "center_name": oc['site_name'], "type": "Stand Alone",
                        "center_fuel": round(fuel), "center_cost": round(cost),
                        "pct": 1.0, "ocean_cost": round(cost),
                        "days": days, "price": cmhl_price,
                    })
                else:
                    # Shopping center — use CP center data × %
                    ctr = conn.execute("SELECT COALESCE(SUM(total_daily_used),0), COUNT(DISTINCT date) FROM daily_site_summary WHERE site_id=?", (center_cc,)).fetchone()
                    ctr_fuel = ctr[0] if ctr else 0
                    days = ctr[1] if ctr else 0
                    ctr_cost = ctr_fuel * cp_price
                    ocean_cost = ctr_cost * pct
                    results.append({
                        "ocean_site": oid, "ocean_name": oc['site_name'], "site_code": oc.get('site_code',''),
                        "center_cc": center_cc, "center_name": center_name, "type": "Shopping Center",
                        "center_fuel": round(ctr_fuel), "center_cost": round(ctr_cost),
                        "pct": round(pct, 4), "ocean_cost": round(ocean_cost),
                        "days": days, "price": cp_price,
                    })

            total_center = sum(r["center_cost"] for r in results)
            total_ocean = sum(r["ocean_cost"] for r in results)

            return {
                "stores": sorted(results, key=lambda x: x["ocean_cost"], reverse=True),
                "total_center_cost": total_center,
                "total_ocean_share": total_ocean,
                "cmhl_price": cmhl_price,
                "cp_price": cp_price,
            }
    except Exception as e:
        return {"stores": [], "total_center_cost": 0, "total_ocean_share": 0, "error": str(e)}


# ---------- 19. Site Info (enriched) ----------

@router.get("/site-info/{site_id}")
def site_info(site_id: str, user: dict = Depends(get_current_user)):
    """Get enriched site info including store master data."""
    try:
        with get_db() as conn:
            row = conn.execute("""
                SELECT s.*, sm.gold_code as sm_gold_code, sm.store_name as sm_store_name,
                       sm.segment_name as sm_segment, sm.channel as sm_channel,
                       d.yearly_expense_mmk_mil, d.daily_avg_expense_mmk, d.pct_on_sales
                FROM sites s
                LEFT JOIN store_master sm ON s.cost_center_code = sm.cost_center_code
                LEFT JOIN diesel_expense_ly d ON s.cost_center_code = d.cost_center_code
                WHERE s.site_id = ?
            """, (site_id,)).fetchone()
            if not row:
                return {}
            return dict(row)
    except Exception:
        return {}


# ---------- 20. Allocated Sites (CP Center Allocation) ----------

@router.get("/sector-sites/allocated")
def get_allocated_sites(
    date_to: str = None,
    site_type: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get CMHL sites that use CP center allocation.
    Returns the SAME field structure as /sector-sites plus center_id, center_name, allocation_pct.
    """
    with get_db() as conn:
        # Get allocation mappings
        alloc_type_filter = ""
        alloc_type_params = []
        if site_type and site_type != 'All':
            alloc_type_filter = " WHERE s.site_type = ?"
            alloc_type_params = [site_type]
        allocs = conn.execute(f"""
            SELECT a.store_cost_center, a.store_name, a.center_cost_center,
                   a.center_name, a.allocation_pct,
                   s.site_id, s.site_name, s.cost_center_code, s.sector_id,
                   s.site_type, s.company, s.region, s.segment_name,
                   s.cost_center_description, s.address_state, s.address_township,
                   s.store_size, s.channel, s.latitude, s.longitude
            FROM store_center_allocation a
            LEFT JOIN sites s ON a.store_cost_center = s.cost_center_code
            {alloc_type_filter}
        """, alloc_type_params).fetchall()

        if not allocs:
            return []

        # Get latest ops date
        _row = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()
        max_date = date_to or (_row[0] if _row else None)
        if not max_date:
            return []

        # Get CP price
        cp_price = conn.execute(
            "SELECT price_per_liter FROM fuel_purchases WHERE sector_id='CP' ORDER BY date DESC LIMIT 1"
        ).fetchone()
        price = cp_price[0] if cp_price else 0

        # Get latest sales date for CMHL
        _row = conn.execute("SELECT MAX(date) FROM daily_sales WHERE sector_id='CMHL'").fetchone()
        max_sales = _row[0] if _row else None

        result = []
        for row in allocs:
            store_cc = row[0]
            center_cc = row[2]
            center_name = row[3]
            alloc_pct = row[4]
            site_id = row[5]
            site_name = row[6] or row[1]
            cost_center_code = row[7] or store_cc

            if not site_id:
                continue  # store not in DB

            a = alloc_pct / 100

            # Center latest data
            c = conn.execute("""
                SELECT total_gen_run_hr, total_daily_used, blackout_hr, spare_tank_balance
                FROM daily_site_summary WHERE site_id = ? AND date = ?
            """, (center_cc, max_date)).fetchone()

            # Center 3d avg data (fuel, tank, gen_hr, blackout)
            c3 = conn.execute("""
                SELECT AVG(total_daily_used), AVG(spare_tank_balance),
                       AVG(total_gen_run_hr), AVG(blackout_hr)
                FROM (
                    SELECT total_daily_used, spare_tank_balance, total_gen_run_hr, blackout_hr
                    FROM daily_site_summary
                    WHERE site_id = ? AND date >= date(?, '-3 days') AND date < ?
                    ORDER BY date DESC
                )
            """, (center_cc, max_date, max_date)).fetchone()

            if c:
                ctr_gen_hr_1d = c[0] or 0
                ctr_fuel_1d = c[1] or 0
                ctr_bo_1d = c[2] or 0
                ctr_tank_1d = c[3] or 0
            else:
                ctr_gen_hr_1d = ctr_fuel_1d = ctr_bo_1d = ctr_tank_1d = 0

            ctr_fuel_3d = (c3[0] or 0) if c3 else 0
            ctr_tank_3d = (c3[1] or 0) if c3 else 0
            ctr_gen_hr_3d = (c3[2] or 0) if c3 else 0
            ctr_bo_3d = (c3[3] or 0) if c3 else 0

            # Blackout: 100% shared (not allocated)
            blackout_1d = ctr_bo_1d
            blackout_3d = ctr_bo_3d

            # Gen Hr: 100% shared (not allocated)
            gen_hr_1d = ctr_gen_hr_1d
            gen_hr_3d = ctr_gen_hr_3d

            # Tank: allocated
            tank_1d = ctr_tank_1d * a
            tank_3d = ctr_tank_3d * a

            # Fuel: allocated
            fuel_1d = ctr_fuel_1d * a
            fuel_3d = ctr_fuel_3d * a

            # Buffer = allocated tank_1d / allocated fuel_3d
            buffer = round(tank_1d / fuel_3d, 1) if fuel_3d > 0 else 0

            # Efficiency = center fuel / center gen_hr (physical rate, NOT allocated)
            efficiency = round(ctr_fuel_1d / ctr_gen_hr_1d, 1) if ctr_gen_hr_1d > 0 else 0

            # Cost
            cost_1d = fuel_1d * price
            cost_3d = fuel_3d * price

            # Sales via cost_center_code (same as SECTOR_SITES)
            sales_1d = 0
            sales_3d = 0
            sales_total = 0
            if max_sales:
                s1 = conn.execute("""
                    SELECT COALESCE(SUM(sales_amt), 0) FROM daily_sales
                    WHERE site_id = ? AND date = ?
                """, (site_id, max_sales)).fetchone()
                sales_1d = s1[0] if s1 else 0

                s3 = conn.execute("""
                    SELECT COALESCE(SUM(sales_amt), 0) / MAX(1, COUNT(DISTINCT date))
                    FROM daily_sales
                    WHERE site_id = ? AND date >= date(?, '-3 days') AND date < ?
                """, (site_id, max_sales, max_sales)).fetchone()
                sales_3d = s3[0] if s3 else 0

                st = conn.execute("""
                    SELECT COALESCE(SUM(sales_amt), 0) FROM daily_sales
                    WHERE site_id = ?
                """, (site_id,)).fetchone()
                sales_total = st[0] if st else 0

            # Diesel % of sales
            diesel_pct_1d = round(cost_1d / sales_1d * 100, 2) if sales_1d > 0 else 0
            diesel_pct_3d = round(cost_3d / sales_3d * 100, 2) if sales_3d > 0 else 0

            # Margin
            margin_1d = sales_1d - cost_1d
            margin_3d = sales_3d - cost_3d

            # Get LY baseline data for this store
            ly_row = conn.execute(
                "SELECT daily_avg_expense_mmk, pct_on_sales FROM diesel_expense_ly WHERE cost_center_code = ?",
                (store_cc,)
            ).fetchone()
            ly_daily_cost = round((ly_row[0] or 0), 0) if ly_row else 0
            ly_pct_on_sales = round((ly_row[1] or 0) * 100, 2) if ly_row else 0

            result.append({
                "site_id": site_id,
                "site_name": site_name,
                "cost_center_code": cost_center_code,
                "center_id": center_cc,
                "center_name": center_name,
                "allocation_pct": alloc_pct,
                "price": price,
                # Populated: Blackout Hr, Diesel Cost, Diesel %
                "blackout_1d": round(blackout_1d, 1),
                "blackout_3d": round(blackout_3d, 1),
                "cost_1d": round(cost_1d, 0),
                "cost_3d": round(cost_3d, 0),
                "diesel_pct_1d": diesel_pct_1d,
                "diesel_pct_3d": diesel_pct_3d,
                # Populated: Sales (needed for diesel % context)
                "sales_1d": round(sales_1d, 0),
                "sales_3d": round(sales_3d, 0),
                "sales_total": round(sales_total, 0),
                "margin_1d": round(margin_1d, 0),
                "margin_3d": round(margin_3d, 0),
                # Not populated — columns kept but empty
                "gen_hr_1d": None, "gen_hr_3d": None,
                "tank_1d": None, "tank_3d": None,
                "fuel_1d": None, "fuel_3d": None,
                "buffer": None, "efficiency": None,
                "center_blackout_1d": None, "center_gen_hr_1d": None,
                "center_tank_1d": None, "center_fuel_1d": None, "center_cost_1d": None,
                "ly_daily_cost": None, "ly_pct_on_sales": None,
            })

        return result


# ---------- 21. Detect Allocated Sites (4-check logic) ----------

@router.get("/sector-sites/detect-allocated")
def detect_allocated_sites(user: dict = Depends(get_current_user)):
    """Detect CMHL stores that need CP center allocation (4-check logic)."""
    with get_db() as conn:
        sites = conn.execute("""
            SELECT s.site_id, s.site_name, s.cost_center_code,
                g.model_name, g.consumption_per_hour,
                (SELECT COUNT(*) FROM generators WHERE site_id = s.site_id) as gen_count,
                (SELECT COALESCE(SUM(total_daily_used), 0) FROM daily_site_summary WHERE site_id = s.site_id) as total_fuel
            FROM sites s
            LEFT JOIN generators g ON s.site_id = g.site_id
            WHERE s.sector_id = 'CMHL'
            GROUP BY s.site_id
        """).fetchall()

        detected = []
        for s in sites:
            model = s[3] or ''
            lph = s[4] or 0
            gens = s[5]
            fuel = s[6]

            c1 = model in ('UNKNOWN', '')
            c2 = fuel == 0
            c3 = lph == 0
            c4 = gens == 1

            if c1 and c2 and c3 and c4:
                # Check if already in allocation table
                existing = conn.execute(
                    "SELECT allocation_pct, center_cost_center FROM store_center_allocation WHERE store_cost_center = ?",
                    (s[2],)
                ).fetchone()

                detected.append({
                    "site_id": s[0],
                    "site_name": s[1],
                    "cost_center_code": s[2],
                    "mapped": existing is not None,
                    "allocation_pct": existing[0] if existing else None,
                    "center_id": existing[1] if existing else None,
                })

        return detected
