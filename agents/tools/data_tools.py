"""
Agent tools 1-6: Data query tools.
"""
import pandas as pd
from agents.tools.registry import tool
from utils.database import get_db


@tool(
    name="query_sites",
    description="List sites, optionally filtered by sector or buffer status. Returns site_id, sector_id, site_type.",
    parameters={
        "type": "object",
        "properties": {
            "sector_id": {"type": "string", "description": "Filter by sector (CP, CMHL, CFC, PG)"},
            "buffer_below": {"type": "number", "description": "Only sites with buffer below this many days"},
        },
    },
)
def query_sites(sector_id=None, buffer_below=None):
    with get_db() as conn:
        query = """
            SELECT s.site_id, s.sector_id, s.site_type,
                   dss.days_of_buffer, dss.spare_tank_balance, dss.total_daily_used
            FROM sites s
            LEFT JOIN daily_site_summary dss ON s.site_id = dss.site_id
                AND dss.date = (SELECT MAX(date) FROM daily_site_summary)
        """
        params = []
        conditions = []
        if sector_id:
            conditions.append("s.sector_id = ?")
            params.append(sector_id)
        if buffer_below is not None:
            conditions.append("dss.days_of_buffer < ?")
            params.append(buffer_below)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY dss.days_of_buffer ASC NULLS LAST"
        return pd.read_sql_query(query, conn, params=params)


@tool(
    name="query_generators",
    description="List generators, optionally filtered by site, model, or minimum KVA capacity.",
    parameters={
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "Filter by site ID"},
            "model_name": {"type": "string", "description": "Filter by model name (partial match)"},
            "min_kva": {"type": "number", "description": "Minimum KVA capacity"},
        },
    },
)
def query_generators(site_id=None, model_name=None, min_kva=None):
    with get_db() as conn:
        query = """
            SELECT g.generator_id, g.site_id, s.sector_id, g.model_name,
                   g.power_kva, g.consumption_per_hour, g.fuel_type, g.supplier
            FROM generators g
            JOIN sites s ON g.site_id = s.site_id
            WHERE g.is_active = 1
        """
        params = []
        if site_id:
            query += " AND g.site_id = ?"
            params.append(site_id)
        if model_name:
            query += " AND g.model_name LIKE ?"
            params.append(f"%{model_name}%")
        if min_kva is not None:
            query += " AND g.power_kva >= ?"
            params.append(min_kva)
        query += " ORDER BY g.site_id, g.model_name"
        return pd.read_sql_query(query, conn, params=params)


@tool(
    name="query_daily_ops",
    description="Get daily operations data for a date range, optionally filtered by site or generator.",
    parameters={
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "Filter by site ID"},
            "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
        },
    },
)
def query_daily_ops(site_id=None, date_from=None, date_to=None):
    with get_db() as conn:
        query = """
            SELECT do.date, do.site_id, g.model_name, do.gen_run_hr,
                   do.daily_used_liters, do.spare_tank_balance, do.blackout_hr
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            WHERE 1=1
        """
        params = []
        if site_id:
            query += " AND do.site_id = ?"
            params.append(site_id)
        if date_from:
            query += " AND do.date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND do.date <= ?"
            params.append(date_to)
        query += " ORDER BY do.date DESC, do.site_id LIMIT 100"
        return pd.read_sql_query(query, conn, params=params)


@tool(
    name="query_fuel_prices",
    description="Get fuel purchase prices, optionally filtered by sector, supplier, date range, or region.",
    parameters={
        "type": "object",
        "properties": {
            "sector_id": {"type": "string", "description": "Filter by sector"},
            "supplier": {"type": "string", "description": "Filter by supplier (Denko, Moon Sun)"},
            "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            "region": {"type": "string", "description": "Filter by region (YGN, MDY)"},
        },
    },
)
def query_fuel_prices(sector_id=None, supplier=None, date_from=None, date_to=None, region=None):
    with get_db() as conn:
        query = """
            SELECT date, sector_id, region, supplier, fuel_type,
                   quantity_liters, price_per_liter
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL
        """
        params = []
        if sector_id:
            query += " AND sector_id = ?"
            params.append(sector_id)
        if supplier:
            query += " AND supplier LIKE ?"
            params.append(f"%{supplier}%")
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        if region:
            query += " AND region = ?"
            params.append(region)
        query += " ORDER BY date DESC LIMIT 100"
        return pd.read_sql_query(query, conn, params=params)


@tool(
    name="get_buffer_status",
    description="Get days-of-buffer for all sites or a specific site. Shows fuel remaining vs daily consumption.",
    parameters={
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "Specific site (omit for all sites)"},
            "max_days": {"type": "number", "description": "Only show sites with buffer below this (default: all)"},
        },
    },
)
def get_buffer_status(site_id=None, max_days=None):
    with get_db() as conn:
        query = """
            SELECT dss.site_id, s.sector_id, dss.date,
                   dss.spare_tank_balance, dss.total_daily_used, dss.days_of_buffer,
                   dss.num_generators_active
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT MAX(date) FROM daily_site_summary WHERE total_daily_used > 0)
        """
        params = []
        if site_id:
            query += " AND dss.site_id = ?"
            params.append(site_id)
        if max_days is not None:
            query += " AND dss.days_of_buffer <= ?"
            params.append(max_days)
        query += " ORDER BY dss.days_of_buffer ASC NULLS LAST"
        return pd.read_sql_query(query, conn, params=params)


@tool(
    name="query_sales_data",
    description="Get daily sales data, optionally filtered by sector, site name, or date range. Returns sales amounts and margins.",
    parameters={
        "type": "object",
        "properties": {
            "sector_id": {"type": "string", "description": "Filter by sector (CP, CMHL, CFC)"},
            "sales_site_name": {"type": "string", "description": "Filter by sales site name (partial match)"},
            "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
        },
    },
)
def query_sales_data(sector_id=None, sales_site_name=None, date_from=None, date_to=None):
    with get_db() as conn:
        query = """
            SELECT date, sales_site_name, sector_id, brand,
                   sales_amt, margin
            FROM daily_sales WHERE 1=1
        """
        params = []
        if sector_id:
            query += " AND sector_id = ?"
            params.append(sector_id)
        if sales_site_name:
            query += " AND sales_site_name LIKE ?"
            params.append(f"%{sales_site_name}%")
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        query += " ORDER BY date DESC LIMIT 200"
        return pd.read_sql_query(query, conn, params=params)


@tool(
    name="compare_energy_vs_sales",
    description="Compare energy (fuel) costs against sales revenue per BCP site. Shows energy cost, sales (for mapped sites), energy % of sales, and recommendation (OPEN/MONITOR/REDUCE/CLOSE). Only sites with exact name match between BCP and sales data show energy %.",
    parameters={
        "type": "object",
        "properties": {
            "sector_id": {"type": "string", "description": "Filter by sector (optional)"},
            "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            "matched_only": {"type": "boolean", "description": "Only show sites with sales data (default: false)"},
        },
    },
)
def compare_energy_vs_sales(sector_id=None, date_from=None, date_to=None, matched_only=False):
    from models.energy_cost import get_store_economics
    result = get_store_economics(date_from=date_from, date_to=date_to)
    if isinstance(result, pd.DataFrame) and not result.empty:
        if sector_id:
            result = result[result["sector_id"] == sector_id]
        if matched_only:
            result = result[result["has_sales"] == True]
        return result[["site_id", "sector_id", "num_generators", "total_liters",
                        "energy_cost", "has_sales", "total_sales", "energy_pct", "recommendation"]]
    return {"message": "No energy data found. Upload blackout Excel files first."}


@tool(
    name="get_hourly_sales_pattern",
    description="Get average sales and transaction counts by hour of day. Useful for comparing peak sales hours against generator run hours.",
    parameters={
        "type": "object",
        "properties": {
            "sector_id": {"type": "string", "description": "Filter by sector (optional)"},
            "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
        },
    },
)
def get_hourly_sales_pattern_tool(sector_id=None, date_from=None, date_to=None):
    from models.energy_cost import get_hourly_sales_pattern
    return get_hourly_sales_pattern(sector_id=sector_id, date_from=date_from, date_to=date_to)


@tool(
    name="get_sector_summary",
    description="Get aggregate KPIs per sector: total sites, generators, avg fuel use, avg buffer days.",
    parameters={
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Date to summarize (default: latest)"},
        },
    },
)
def get_sector_summary(date=None):
    with get_db() as conn:
        if not date:
            date = conn.execute("SELECT MAX(date) FROM daily_site_summary WHERE total_daily_used > 0").fetchone()[0]
        if not date:
            return {"error": "No data available"}

        df = pd.read_sql_query("""
            SELECT s.sector_id,
                   COUNT(DISTINCT dss.site_id) as sites,
                   SUM(dss.num_generators_active) as active_generators,
                   ROUND(SUM(dss.total_daily_used), 0) as total_fuel_used_liters,
                   ROUND(SUM(dss.spare_tank_balance) * 1.0 / NULLIF(SUM(dss.total_daily_used), 0), 1) as avg_buffer_days,
                   MIN(dss.days_of_buffer) as min_buffer_days,
                   ROUND(SUM(dss.total_gen_run_hr), 1) as total_gen_hours
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = ?
            GROUP BY s.sector_id
            ORDER BY s.sector_id
        """, conn, params=(date,))
        return df
