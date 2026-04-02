# CLAUDE.md — Project Guide for AI Assistants

## What is this project?

CityBCPAgent is a Business Continuity Planning dashboard for managing backup generators and fuel supply across 55+ sites in Myanmar. It helps decision-makers during power outages and diesel shortages. It also compares energy (fuel) costs against sales revenue to recommend whether stores should stay open.

## Tech Stack
- **Frontend:** Streamlit 1.50 + streamlit-shadcn-ui 0.1.19 + Plotly
- **Database:** SQLite with WAL mode (db/bcp.db) — starts empty, user uploads all data
- **ML:** scikit-learn (Ridge, Isolation Forest, GradientBoosting)
- **AI:** Claude Haiku 4.5 via OpenRouter (cheapest Claude model)
- **Auth:** Session tokens stored in DB + URL query params
- **Container:** Docker on port 8501

## Project Structure
```
app.py                  — Home page (requires login)
config/settings.py      — Sectors, thresholds, energy decision matrix, brand/segment maps
db/                     — SQLite database (empty on first run, auto-created)
utils/database.py       — 19 tables, WAL mode, all CRUD helpers
utils/auth.py           — Login, roles (super_admin/admin/user), persistent sessions
utils/ai_insights.py    — AI analysis: DB-cached, one-button generation per page
utils/llm_client.py     — OpenRouter (primary) + Anthropic (fallback) LLM client
utils/email_sender.py   — SMTP alerts, UI-configurable
utils/charts.py         — 12 reusable Plotly chart builders
utils/smart_table.py    — HTML tables with severity badges
utils/kpi_card.py       — KPI cards with calculation transparency
utils/page_header.py    — Consistent dark gradient header across all pages
parsers/blackout_parser.py  — Parses Blackout Hr_ Excel files (dynamic columns)
parsers/fuel_price_parser.py — Parses Daily Fuel Price.xlsx (4 sheets)
parsers/name_normalizer.py  — Fixes generator name typos
parsers/sales_parser.py     — Parses daily + hourly sales Excel files
parsers/storemaster_parser.py — Parses store master reference data
models/decision_engine.py   — 15 Tier 1-3 predictions + energy-aware operating modes
models/energy_cost.py       — Energy cost vs sales: sector comparison, site breakdown, decision matrix
models/fuel_price_forecast.py — Ridge regression, 7-day price forecast
models/buffer_predictor.py   — Exponential smoothing, stockout projection
models/efficiency_scorer.py  — Isolation Forest anomaly detection
models/bcp_engine.py        — Weighted composite BCP scoring (A-F grades)
models/blackout_predictor.py — GradientBoosting for blackout probability
agents/chat_agent.py    — Tool-calling AI chat with 15 tools
agents/tools/           — data_tools.py (9 query tools), model_tools.py (6 ML tools)
alerts/alert_engine.py  — 11 alert conditions with escalation (incl. energy cost alerts)
pages/00-11             — 12 Streamlit pages (ops, analysis, data quality)
pages/12_Sales_vs_Energy.py — Sales vs Energy: 7-tab analysis page
seed_database.py        — One-time Excel → SQLite migration (not used in Docker)
```

## Key Patterns

### Every page follows this pattern:
```python
import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.auth import require_login, render_sidebar_user
from utils.page_header import render_page_header
from utils.ai_insights import render_insight_panel, finish_page

st.set_page_config(...)
require_login()
render_sidebar_user()
render_page_header(icon, title, description)

# ... page content with charts, tables ...
render_insight_panel(context, data, unique_key)  # after each chart/table

finish_page()  # at the very end — shows AI generate button
```

### Database access:
```python
from utils.database import get_db
with get_db() as conn:
    df = pd.read_sql_query("SELECT ...", conn)
```

### AI insights:
- `render_insight_panel()` queues for generation
- `render_page_summary()` queues page-level summary
- `finish_page()` shows the "Generate AI Analysis" button
- Insights are cached in `ai_insights_cache` DB table with timestamps
- "Refresh All Analysis" clears cache and regenerates

### Authentication:
- Session token in URL: `?session=abc123`
- Token validated against `sessions` table in DB
- Survives browser refresh (24hr expiry)
- Roles: super_admin > admin > user
- Super admin credentials from .env (SUPER_ADMIN_USER/PASS)

### Data upload:
- **No pre-seeded data** — database starts empty, user uploads everything via Data Entry
- Full Replace Mode for ops data: clears daily_operations, site_summary, fuel_purchases, alerts, ai_cache
- Sales data uses upsert (append/update, not full replace)
- Keeps: sites, generators, users, settings (structural data)
- Auto-detects file type by Excel sheet names (not filename)
- Supports 7 file types: 3 blackout files, 1 fuel price, daily sales, hourly sales, store master
- Auto-runs alerts after import
- Auto-sends email if SMTP configured

### Sales vs Energy (Page 12):
- Energy and sales are **separate drill-downs** that converge at **sector level only**
- No cross-mapping between sales site names and BCP site names
- Brand→Sector mapping resolves sector from sales data (BRAND_SECTOR_MAP in settings)
- 7 tabs: Sector Comparison, Energy Deep Dive, Sales Deep Dive, Daily Trend, Hourly Analysis, Store Decision, Data Browser
- Decision matrix recommends FULL/MONITOR/REDUCE/CLOSE based on energy % of sales

## Sectors
- **CP** (City Pharmacy): has blackout data
- **CMHL** (City Mart Holdings): no blackout tracking
- **CFC** (City Food Concepts): has blackout tracking but mostly NULL
- **PG**: No active data

## Data Flow
```
Excel files → Parser (clean/validate) → SQLite DB → Dashboard pages
                                                   → ML Models → Predictions
                                                   → AI Agent → Deep insights
                                                   → Alert Engine → Email alerts
                                                   → Energy Cost Model → Sales vs Energy
```

## Common Tasks

### Add a new page:
1. Create `pages/XX_Name.py`
2. Follow the pattern above (auth + header + content + finish_page)
3. Add navigation entry in `app.py` NAV list

### Add a new ML model:
1. Create `models/new_model.py` with a main function
2. Add a tool in `agents/tools/model_tools.py` using @tool decorator
3. Call from relevant page

### Add a new alert condition:
1. Add check function in `alerts/alert_engine.py`
2. Call it from `run_all_checks()`
3. Add threshold to `config/settings.py` ALERTS dict

### Add a new database table:
1. Add CREATE TABLE to SCHEMA string in `utils/database.py`
2. Add CRUD helpers below
3. Table auto-creates on next run (init_db runs on import)

## Data Quality
The Data Quality page (11_Data_Quality.py) runs 8 automated checks on every load:
1. **Generator Specs vs Actual** — compares rated L/hr against actual usage from operations data
2. **Spec Inconsistency** — same model with different consumption rates across sites
3. **Unknown Generators** — model name not recognized, no specs
4. **Null Consumption** — generators missing consumption per hour
5. **Buffer Anomalies** — sites with >500 buffer days (near-zero usage)
6. **Idle Sites** — fuel in tank but generators never ran
7. **Reporting Gaps** — dates where <50% of sites reported data
8. **Tank Balance Inconsistency** — different generators report different tank levels

Issues are grouped by source Excel file with exact column references.

### Buffer calculation:
- **Correct:** `SUM(spare_tank_balance) / NULLIF(SUM(total_daily_used), 0)` at sector level
- **Wrong:** `AVG(days_of_buffer)` — cannot average ratios, outliers (2000+ day buffer) skew results

### Efficiency calculation:
- **Correct:** `actual_used / (rated_consumption * run_hours) * 100`
- **Wrong:** `(rated_consumption * run_hours) / actual_used * 100` — inverted formula

### Energy cost calculation:
- `energy_cost = daily_used_liters * fuel_price_per_liter`
- `energy_pct = (energy_cost / sales_value) * 100`
- Thresholds: <5% HEALTHY, 5-15% MONITOR, 15-30% REDUCE, 30-60% CRITICAL, >60% CLOSE

## Environment Variables
```
OPENROUTER_API_KEY    — Required for AI features
SUPER_ADMIN_USER      — Default: admin
SUPER_ADMIN_PASS      — Default: admin123
SUPER_ADMIN_EMAIL     — Optional
```

## Docker
```bash
docker compose up -d --build     # Build and run (empty DB, upload data via UI)
docker compose down              # Stop
docker compose down -v           # Stop + delete DB volume (full reset)
docker logs city-bcp-agent       # View logs
docker exec city-bcp-agent python3 -c "..."  # Run commands inside
```
