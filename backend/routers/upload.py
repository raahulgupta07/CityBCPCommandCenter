"""Upload router — history, store summary, raw data browser, clear actions."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
import pandas as pd
from utils.database import get_db
from backend.routers.auth import get_current_user, require_admin

router = APIRouter()


def _df(df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return df.fillna("").to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════
# Last Sync per file type
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/upload/last-sync")
def last_sync(user: dict = Depends(require_admin)):
    """Check sync status using actual DB row counts + upload history timestamps."""
    # Map card keys to DB queries that check if data exists
    checks = {
        "blackout_cmhl": ("SELECT COUNT(*) FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id WHERE s.sector_id = 'CMHL'", "CMHL"),
        "blackout_cp": ("SELECT COUNT(*) FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id WHERE s.sector_id = 'CP'", "CP"),
        "blackout_cfc": ("SELECT COUNT(*) FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id WHERE s.sector_id = 'CFC'", "CFC"),
        "blackout_pg": ("SELECT COUNT(*) FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id WHERE s.sector_id = 'PG'", "PG"),
        "fuel_price": ("SELECT COUNT(*) FROM fuel_purchases", None),
        "combo_sales": ("SELECT COUNT(*) FROM daily_sales", None),
        "diesel_expense_ly": ("SELECT COUNT(*) FROM diesel_expense_ly", None),
        "store_allocation": ("SELECT COUNT(*) FROM store_center_allocation", None),
    }

    result = {}
    with get_db() as conn:
        for key, (query, sector) in checks.items():
            try:
                count = conn.execute(query).fetchone()[0]
            except Exception:
                count = 0

            # Get latest timestamp from upload_history or sites updated_at
            ts = None
            if key.startswith("blackout_") and sector:
                ts_row = conn.execute(
                    "SELECT MAX(updated_at) FROM sites WHERE sector_id = ?", (sector,)
                ).fetchone()
                ts = ts_row[0][:16] if ts_row and ts_row[0] else None
            if not ts:
                # Fallback: check upload_history
                ft_variants = {
                    "combo_sales": ['daily_sales','hourly_sales','combo_sales','sales','sales_reference','hourly_reference'],
                    "diesel_expense_ly": ['diesel_expense_ly','diesel_expense'],
                }
                if key in ft_variants:
                    variants_list = ft_variants[key]
                    placeholders = ",".join(["?"] * len(variants_list))
                    hist = conn.execute(
                        f"SELECT uploaded_at FROM upload_history WHERE file_type IN ({placeholders}) ORDER BY uploaded_at DESC LIMIT 1",
                        variants_list
                    ).fetchone()
                else:
                    hist = conn.execute(
                        "SELECT uploaded_at FROM upload_history WHERE LOWER(file_type) = LOWER(?) ORDER BY uploaded_at DESC LIMIT 1", (key,)
                    ).fetchone()
                ts = hist[0][:16] if hist and hist[0] else None

            if count > 0:
                result[key] = {"rows": count, "synced_at": ts or "seeded"}
            else:
                result[key] = None

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Upload history + DB totals
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/upload/history")
def upload_history(user: dict = Depends(require_admin)):
    with get_db() as conn:
        uploads = pd.read_sql_query("""
            SELECT filename, file_type, sector_id, rows_parsed, rows_accepted,
                   rows_rejected, date_range_start, date_range_end, uploaded_at
            FROM upload_history ORDER BY uploaded_at DESC
        """, conn)
        totals = {}
        # Hardcoded whitelist — safe to interpolate into SQL
        ALLOWED_TABLES = {"sites", "generators", "daily_operations", "daily_site_summary",
                          "fuel_purchases", "daily_sales", "hourly_sales", "store_master",
                          "alerts", "upload_history", "sectors", "users", "sessions",
                          "diesel_expense_ly", "site_sales_map", "generator_name_map"}
        for t in ["sites", "generators", "daily_operations", "fuel_purchases",
                   "daily_sales", "hourly_sales", "store_master", "diesel_expense_ly"]:
            assert t in ALLOWED_TABLES, f"Invalid table: {t}"
            try:
                _row = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
                totals[t] = _row[0] if _row else 0
            except Exception:
                totals[t] = 0
    return {"uploads": _df(uploads), "totals": totals}


# ═══════════════════════════════════════════════════════════════════════════
# Store Summary (pivot: site × date × metric)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/upload/store-summary")
def store_summary(
    sector: Optional[str] = None,
    metric: str = "total_daily_used",
    user: dict = Depends(require_admin),
):
    allowed_metrics = {
        "total_gen_run_hr": "Gen Run Hours",
        "total_daily_used": "Daily Diesel Used (L)",
        "spare_tank_balance": "Tank Balance (L)",
        "blackout_hr": "Blackout Hours",
        "days_of_buffer": "Buffer Days",
        "num_generators_active": "Active Generators",
    }
    if metric not in allowed_metrics:
        raise HTTPException(400, f"Metric must be one of: {', '.join(allowed_metrics.keys())}")

    with get_db() as conn:
        q = """
            SELECT dss.date, dss.site_id, s.sector_id, dss.""" + metric + """ as value
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE 1=1
        """
        params = []
        if sector:
            q += " AND s.sector_id = ?"; params.append(sector)
        q += " ORDER BY s.sector_id, dss.site_id, dss.date"
        df = pd.read_sql_query(q, conn, params=params)

    if df.empty:
        return {"pivot": [], "dates": [], "sites": [], "metric_label": allowed_metrics[metric]}

    # Pivot: rows = site_id, columns = date
    pivot = df.pivot_table(index="site_id", columns="date", values="value", aggfunc="sum")
    dates = sorted(df["date"].unique().tolist())
    pivot = pivot.reindex(columns=dates)

    # Convert to list of dicts for frontend
    rows = []
    for site_id in pivot.index:
        row = {"site_id": site_id}
        sector_id = df[df["site_id"] == site_id]["sector_id"].iloc[0]
        row["sector_id"] = sector_id
        for d in dates:
            try:
                val = pivot.loc[site_id, d]
            except KeyError:
                val = None
            row[d] = round(float(val), 1) if pd.notna(val) else None
        rows.append(row)

    return {
        "pivot": rows,
        "dates": dates,
        "sites": list(pivot.index),
        "metric": metric,
        "metric_label": allowed_metrics[metric],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Raw Data Browser
# ═══════════════════════════════════════════════════════════════════════════

TABLE_QUERIES = {
    "sites": "SELECT s.site_id, s.sector_id, s.site_type, s.site_name, s.cost_center_code FROM sites s ORDER BY s.sector_id, s.site_id",
    "generators": "SELECT g.site_id, s.sector_id, g.model_name, g.power_kva, g.consumption_per_hour, g.fuel_type, g.supplier FROM generators g JOIN sites s ON g.site_id = s.site_id ORDER BY s.sector_id, g.site_id",
    "daily_ops": "SELECT do.date, do.site_id, g.model_name, do.gen_run_hr, do.daily_used_liters, do.spare_tank_balance, do.blackout_hr FROM daily_operations do JOIN generators g ON do.generator_id = g.generator_id ORDER BY do.date DESC, do.site_id LIMIT 500",
    "site_summary": "SELECT dss.date, dss.site_id, s.sector_id, dss.total_gen_run_hr, dss.total_daily_used, dss.spare_tank_balance, dss.days_of_buffer FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id ORDER BY dss.date DESC LIMIT 500",
    "fuel_prices": "SELECT date, sector_id, region, supplier, fuel_type, quantity_liters, price_per_liter FROM fuel_purchases ORDER BY date DESC LIMIT 200",
    "daily_sales": "SELECT date, sales_site_name, sector_id, brand, sales_amt, margin FROM daily_sales ORDER BY date DESC LIMIT 500",
    "hourly_sales": "SELECT date, hour, sales_site_name, sector_id, brand, sales_amt, trans_cnt FROM hourly_sales ORDER BY date DESC, hour LIMIT 500",
    "store_master": "SELECT gold_code, store_name, cost_center_code, segment_name, sector_id, channel, address_state FROM store_master ORDER BY sector_id LIMIT 500",
    "alerts": "SELECT alert_type, severity, site_id, sector_id, message, is_acknowledged, created_at FROM alerts ORDER BY created_at DESC LIMIT 200",
    "uploads": "SELECT filename, file_type, sector_id, rows_parsed, rows_accepted, rows_rejected, uploaded_at FROM upload_history ORDER BY uploaded_at DESC",
}


@router.get("/upload/raw/{table}")
def raw_data(
    table: str,
    search: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    if table not in TABLE_QUERIES:
        raise HTTPException(400, f"Table must be one of: {', '.join(TABLE_QUERIES.keys())}")

    with get_db() as conn:
        df = pd.read_sql_query(TABLE_QUERIES[table], conn)

    if search and not df.empty:
        mask = df.astype(str).apply(lambda row: row.str.contains(search, case=False).any(), axis=1)
        df = df[mask]

    return {"rows": _df(df), "count": len(df), "table": table}


# ═══════════════════════════════════════════════════════════════════════════
# Data Quality Validation — Excel vs DB comparison per sector
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/upload/validation")
def data_validation(user: dict = Depends(get_current_user)):
    """Compare DB totals against cached Excel totals for all sectors."""
    sectors = []
    with get_db() as conn:
        # Ensure table exists
        conn.execute("""CREATE TABLE IF NOT EXISTS excel_validation_cache (
            sector_id TEXT NOT NULL, date TEXT NOT NULL,
            gen_hr REAL DEFAULT 0, fuel REAL DEFAULT 0,
            tank REAL DEFAULT 0, blackout REAL DEFAULT 0,
            uploaded_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (sector_id, date))""")

        for sector_id in ["CFC", "CMHL", "CP", "PG"]:
            # Site/gen counts
            n_sites = conn.execute("SELECT COUNT(*) FROM sites WHERE sector_id=?", (sector_id,)).fetchone()[0]
            if n_sites == 0:
                continue
            n_gens = conn.execute(
                "SELECT COUNT(*) FROM generators WHERE site_id IN (SELECT site_id FROM sites WHERE sector_id=?)",
                (sector_id,)
            ).fetchone()[0]

            # DB totals per date
            db_rows = conn.execute("""
                SELECT dss.date,
                    ROUND(SUM(dss.total_gen_run_hr),1) as gen_hr,
                    ROUND(SUM(dss.total_daily_used),1) as fuel,
                    ROUND(SUM(dss.spare_tank_balance),0) as tank,
                    ROUND(SUM(dss.blackout_hr),1) as blackout,
                    COUNT(DISTINCT dss.site_id) as sites
                FROM daily_site_summary dss
                JOIN sites s ON s.site_id = dss.site_id
                WHERE s.sector_id = ?
                GROUP BY dss.date ORDER BY dss.date
            """, (sector_id,)).fetchall()

            # Excel totals from cache
            excel_rows = conn.execute("""
                SELECT date, gen_hr, fuel, tank, blackout
                FROM excel_validation_cache
                WHERE sector_id = ?
                ORDER BY date
            """, (sector_id,)).fetchall()
            excel_map = {r[0]: {"gen_hr": r[1] or 0, "fuel": r[2] or 0, "tank": r[3] or 0, "blackout": r[4] or 0} for r in excel_rows}

            # Build comparison rows
            rows = []
            for db_row in db_rows:
                d = db_row[0]
                db = {"gen_hr": db_row[1] or 0, "fuel": db_row[2] or 0, "tank": db_row[3] or 0, "blackout": db_row[4] or 0}
                e = excel_map.get(d, {"gen_hr": 0, "fuel": 0, "tank": 0, "blackout": 0})
                has_excel = d in excel_map
                pass_check = all(abs(e[k] - db[k]) < 2 for k in ["gen_hr", "fuel", "tank", "blackout"]) if has_excel else True
                diff = {k: round(db[k] - e[k], 1) for k in ["gen_hr", "fuel", "tank", "blackout"]}
                rows.append({
                    "date": d,
                    "sites": db_row[5],
                    "excel": {k: round(e[k], 1) for k in ["gen_hr", "fuel", "tank", "blackout"]},
                    "db": {k: round(db[k], 1) for k in ["gen_hr", "fuel", "tank", "blackout"]},
                    "diff": diff,
                    "pass": pass_check,
                    "has_excel": has_excel,
                })

            # Count passes
            total_pass = sum(1 for r in rows if r["pass"])
            sectors.append({
                "sector": sector_id,
                "sites": n_sites,
                "generators": n_gens,
                "rows": rows,
                "total_dates": len(rows),
                "pass_count": total_pass,
                "issues": [],
            })
    return {"sectors": sectors}


# ═══════════════════════════════════════════════════════════════════════════
# Clear data
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/upload/clear/{target}")
def clear_data(target: str, user: dict = Depends(require_admin)):
    def _sector_clear(conn, sec):
        """Full cleanup for a sector: operations → summary → generators → sites → excel cache."""
        conn.execute("DELETE FROM daily_operations WHERE site_id IN (SELECT site_id FROM sites WHERE sector_id=?)", (sec,))
        conn.execute("DELETE FROM daily_site_summary WHERE site_id IN (SELECT site_id FROM sites WHERE sector_id=?)", (sec,))
        conn.execute("DELETE FROM generators WHERE site_id IN (SELECT site_id FROM sites WHERE sector_id=?)", (sec,))
        conn.execute("DELETE FROM sites WHERE sector_id=?", (sec,))
        conn.execute("DELETE FROM excel_validation_cache WHERE sector_id=?", (sec,))

    CLEAR_MAP = {
        "all": [
            "DELETE FROM daily_operations", "DELETE FROM daily_site_summary",
            "DELETE FROM generators", "DELETE FROM sites",
            "DELETE FROM fuel_purchases", "DELETE FROM daily_sales",
            "DELETE FROM hourly_sales", "DELETE FROM alerts", "DELETE FROM ai_insights_cache",
            "DELETE FROM excel_validation_cache", "DELETE FROM store_master",
            "DELETE FROM diesel_expense_ly", "DELETE FROM store_center_allocation",
        ],
        "all_daily": [
            "DELETE FROM daily_operations", "DELETE FROM daily_site_summary",
            "DELETE FROM generators", "DELETE FROM sites",
            "DELETE FROM excel_validation_cache",
        ],
        "all_reference": [
            "DELETE FROM fuel_purchases", "DELETE FROM daily_sales",
            "DELETE FROM hourly_sales", "DELETE FROM store_master",
            "DELETE FROM diesel_expense_ly",
        ],
        "fuel": ["DELETE FROM fuel_purchases"],
        "sales": ["DELETE FROM daily_sales", "DELETE FROM hourly_sales"],
        "store_master": ["DELETE FROM store_master"],
        "diesel_expense": ["DELETE FROM diesel_expense_ly"],
    }
    SECTOR_CLEAR_MAP = {
        "cmhl": "CMHL",
        "cp": "CP",
        "cfc": "CFC",
        "pg": "PG",
    }
    valid_targets = list(CLEAR_MAP.keys()) + list(SECTOR_CLEAR_MAP.keys())
    if target not in valid_targets:
        raise HTTPException(400, f"Target must be one of: {', '.join(valid_targets)}")

    with get_db() as conn:
        if target in SECTOR_CLEAR_MAP:
            _sector_clear(conn, SECTOR_CLEAR_MAP[target])
        else:
            for sql in CLEAR_MAP[target]:
                conn.execute(sql)
        # Only clear alerts/cache for daily data changes (not ref data purges)
        if target not in ("fuel", "sales", "store_master", "diesel_expense", "all_reference"):
            conn.execute("DELETE FROM alerts")
            conn.execute("DELETE FROM ai_insights_cache")

    return {"ok": True, "message": f"Cleared {target} data"}
