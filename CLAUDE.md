# CLAUDE.md — Project Guide for AI Assistants

## What is this project?

CityBCPAgent is a Business Continuity Planning dashboard for managing backup generators and fuel supply across 60+ sites in Myanmar. It helps decision-makers during power outages and diesel shortages. It compares energy (fuel) costs against sales revenue to recommend whether stores should stay open. All features are consolidated into a single **BCP Command Center** page with hierarchical drill-down: Group > Sector (Business Sector) > Company > Site.

## Tech Stack
- **Frontend:** Streamlit 1.50 + streamlit-shadcn-ui 0.1.19 + ECharts (via streamlit-echarts)
- **Database:** SQLite with WAL mode (db/bcp.db) — starts empty, user uploads all data
- **ML:** scikit-learn (Ridge, Isolation Forest, GradientBoosting)
- **AI:** Claude Haiku 4.5 via OpenRouter (cheapest Claude model)
- **Auth:** Session tokens stored in DB + URL query params
- **Container:** Docker on port 8501

## Project Structure
```
app.py                  — Home page (requires login, nav to 4 pages)
config/settings.py      — Sectors, thresholds, energy decision matrix, brand/segment maps
db/                     — SQLite database (empty on first run, auto-created)
utils/database.py       — 20+ tables, WAL mode, all CRUD helpers, auto-migration
utils/auth.py           — Login, roles (super_admin/admin/user), persistent sessions
utils/ai_insights.py    — AI analysis: DB-cached, one-button generation
utils/llm_client.py     — OpenRouter (primary) + Anthropic (fallback) LLM client
utils/email_sender.py   — SMTP alerts, UI-configurable
utils/charts.py         — Plotly chart builders + heatmap color/icon helpers
utils/echarts.py        — ECharts chart builders (bar, line, dual-axis, pie, hbar, grouped, stacked)
utils/smart_table.py    — HTML tables with severity badges + Excel download with icons
utils/kpi_card.py       — KPI cards with calculation transparency
utils/page_header.py    — Consistent dark gradient header across all pages
parsers/blackout_parser.py      — Parses Blackout Hr_ Excel files (CFC, CMHL, CP, PG)
parsers/fuel_price_parser.py    — Parses Daily Fuel Price.xlsx (4 sheets)
parsers/name_normalizer.py      — Fixes generator name typos
parsers/sales_parser.py         — Parses daily + hourly sales (GOLD_CODE, CostCenter, SegmentName)
parsers/storemaster_parser.py   — Parses store master reference data
parsers/diesel_expense_parser.py — Parses LY diesel expense baseline
models/decision_engine.py   — Operating modes, delivery queue, budget, anomalies, transfers, load optimization
models/energy_cost.py       — Store economics: direct site_id query, no JOINs
models/fuel_price_forecast.py — Ridge regression, 7-day price forecast
models/buffer_predictor.py   — Exponential smoothing, stockout projection
models/efficiency_scorer.py  — Isolation Forest anomaly detection
models/bcp_engine.py        — Weighted composite BCP scoring (A-F grades)
models/blackout_predictor.py — GradientBoosting for blackout probability
agents/chat_agent.py    — Tool-calling AI chat with 15 tools
agents/tools/           — data_tools.py (9 query tools), model_tools.py (6 ML tools)
alerts/alert_engine.py  — 11 alert conditions with escalation (incl. energy cost alerts)
pages/05_BCP_Command_Center.py — THE MAIN PAGE: all KPIs, charts, tables, predictions
pages/08_BCP_Chat.py           — AI chat agent (chat only, no summary/alerts tabs)
pages/09_Data_Entry.py         — Upload Excel files (CFC, CMHL, CP, PG, fuel, sales)
pages/10_Settings.py           — User management, SMTP config
```

## Page Architecture — BCP Command Center

The entire dashboard is ONE page (`05_BCP_Command_Center.py`) with tabs:

### Top-level tabs: `[Group | Distribution | F&B | Property | Retail | Dictionary]`
- Tabs are based on `business_sector` column from Blackout Excel files
- Distribution = PG, F&B = CFC, Property = CP, Retail = CMHL

### Group tab shows (in order):
1. **KPI blocks** — TOTAL PERIOD, LAST DAY, LAST 3 DAYS (each with 10 KPI cards + Quick Reference)
2. **Trend charts** — 12+ charts (fuel, gen hours, efficiency, cost, sales, buffer, blackout)
3. **3-Day Rolling Average trends** — 6 dedicated daily-vs-rolling charts
4. **Yesterday vs 3-Day comparison** cards
5. **Recommendations** — rule-based (critical sites, burn spike, diesel% rising)
6. **Sector Heatmap** — aggregated table (one row per sector)
7. **Regular vs LNG comparison** — side-by-side cards + 6 charts
8. **Site Rankings** — Top 15 Diesel% + Top 15 Cost (horizontal bars)
9. **Mapped vs Unmapped** sites tables
10. **Operating Modes** (FULL/REDUCED/CLOSE per site)
11. **Delivery Queue** (urgency + liters needed)
12. **BCP Risk Scores** (A-F grades)
13. **Stockout Forecast** (7-day)
14. **Supplier Buy Signal + Weekly Budget**
15. **Active Alerts**
16. **What-If Simulator**
17. **Fuel Price Intelligence** — price trend, volume, 7-day ML forecast, purchase log
18. **Operations & Fleet** — gen fleet KPIs, transfers, load optimization, maintenance, blackout monitor, anomalies
19. **Peak Hours Heatmap** — hour × day-of-week profitability grid (icons only)
20. **Predictions** — 15 forecasts (fuel, buffer, cost, blackout, theft, delivery, efficiency, etc.)

### Sector tabs (e.g. Retail) show sub-tabs: `[All | CMHL | MCS | Site]`
- **All**: Same as Group but filtered to sector
- **Company tabs** (CMHL, MCS, etc.): Filtered to that company
- **Site**: Dropdown → individual site deep-dive with 22+ charts

### Site level shows:
- Site KPI card (buffer, tank, burn, cost, sales, diesel%)
- Generator Fleet table (specs + latest ops)
- All Trends (buffer, efficiency, gen hours vs fuel, fuel vs tank, cumulative, cost, blackout, sales, diesel%, fuel price, per-generator, anomaly detection, site vs sector comparison)
- Variance analysis (expected vs actual per generator)
- Generator detail table + Expected vs Actual chart + Cost Split pie
- Sales vs Diesel trends (Daily/Weekly/Monthly period selector)
- Peak Hours Heatmap
- Period selector applies to ALL charts (Daily/Weekly/Monthly)

### Dictionary tab:
- Threshold Reference (icons only: 🟢🟡🟠🔴)
- KPI Definitions & Formulas (16 KPIs with formula, source, unit, where used)
- Operating Mode Definitions
- BCP Risk Grades (A-F)
- Alert Severity Levels
- Variance Status
- Peak Hours Heatmap guide
- Icon Reference
- Dashboard Navigation Guide
- Data Sources

### Filters:
- **Date Range** (shadcn calendar, top of page)
- **Site Type** (All / Regular / LNG, next to date range)

## Key Patterns

### Chart number formatting:
- All charts use `_make_rich_data()` in `utils/echarts.py` which formats labels via `{@name}` ECharts pattern
- Numbers: `1.5B`, `36.8M`, `12.3K`, `6,541`, `0.85`
- Sales charts pre-convert to millions (divide by 1e6) before passing to chart
- Dual-axis charts: bar labels shown, line labels hidden (prevent overlap)
- Line charts: labels hidden when >10 points or >2 series
- No JsCode used (streamlit-echarts version doesn't support it)

### Heatmap icons (no background colors):
- All threshold cells use icons only: 🟢🟡🟠🔴⚪
- No background color fills in tables or Excel downloads
- `_get_heatmap_label()` in `utils/charts.py` returns `"🟢 7,262"` format
- `_cc()` helper renders `<td>` with icon + value, no background

### Database access:
```python
from utils.database import get_db
with get_db() as conn:
    df = pd.read_sql_query("SELECT ...", conn)
```

### Authentication:
- Session token in URL: `?session=abc123`
- Token validated against `sessions` table in DB
- Roles: super_admin > admin > user
- Super admin credentials from .env (SUPER_ADMIN_USER/PASS)

### Data upload:
- **No pre-seeded data** — database starts empty, user uploads everything via Data Entry
- Full Replace Mode for ops data: clears daily_operations, site_summary, fuel_purchases, alerts, ai_cache
- Sales data uses upsert (append/update, not full replace)
- Supports: 4 blackout files (CFC, CMHL, CP, PG), 1 fuel price, 1 combo sales file, 1 LY diesel expense
- Auto-detects file type by Excel sheet names
- PG sector fully supported (has_blackout_data: True)

### Hierarchy from Excel data:
```
business_sector (from Excel) → company (from Excel) → site_id → generator_id
Distribution                    PG                     PG-PGWH    PG-PGWH_100KVA
F&B                            CFC                    CFC-SBFTY  CFC-SBFTY_550 KVA-G1
Property                       CPPL, CMHL SC, UCC     CP-xxx     CP-xxx_model
Retail                         CMHL, MCS              CMHL-xxx   CMHL-xxx_model
```

## Sectors
- **CFC** (City Food Concepts): F&B sector, 2 sites, has blackout data
- **CMHL** (City Mart Holdings): Retail sector, 31 sites, has blackout data
- **CP** (City Properties): Property sector, 25 sites, has blackout data
- **PG** (PG Sector): Distribution sector, 2 sites, has blackout data

## Key Formulas
- **Buffer Days:** `SUM(spare_tank_balance) / NULLIF(SUM(total_daily_used), 0)`
- **Diesel Needed:** `SUM(7 × Avg Burn − Tank)` for sites below 7 days
- **Diesel % of Sales:** `(Liters × Price) ÷ Sales × 100`
- **Variance:** `Actual Used − (Rated L/hr × Run Hours)`
- **Efficiency:** `Liters Used ÷ Gen Hours` (normal: flat; spike up = waste/theft)
- **Peak Hours:** `Avg Hourly Sales ÷ Diesel Cost/Hr` (🟢>3×, 🟡>1.5×, 🟠>1×, 🔴<1×)

## Environment Variables
```
OPENROUTER_API_KEY    — Required for AI features
SUPER_ADMIN_USER      — Default: admin
SUPER_ADMIN_PASS      — Default: admin123
SUPER_ADMIN_EMAIL     — Optional
```

## Docker
```bash
docker-compose up -d --build     # Build and run (empty DB, upload data via UI)
docker-compose down              # Stop
docker-compose down -v           # Stop + delete DB volume (full reset)
docker logs city-bcp-agent       # View logs
```
