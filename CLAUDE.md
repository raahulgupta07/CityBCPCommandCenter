# CLAUDE.md — Project Guide for AI Assistants

## What is this project?

CityBCPAgent is a Business Continuity Planning dashboard for managing backup generators and fuel supply across 60+ sites in Myanmar. It helps decision-makers during power outages and diesel shortages by comparing energy (fuel) costs against sales revenue to recommend whether stores should stay open. The app uses a **FastAPI + SvelteKit** architecture with hierarchical drill-down: Group > Sector (Business Sector) > Company > Site.

## Tech Stack
- **Frontend:** SvelteKit 5 (Svelte 5 runes) + adapter-static (SPA mode) + ECharts + TailwindCSS 4
- **Backend:** FastAPI (Python 3.12) serving both API (`/api/*`) and static frontend
- **Database:** SQLite with WAL mode (`db/bcp.db`) — starts empty, user uploads all data
- **ML:** scikit-learn (Ridge, Isolation Forest, GradientBoosting)
- **AI:** Gemini 3.1 Flash Lite via OpenRouter (google/gemini-3.1-flash-lite-preview)
- **Auth:** JWT tokens (python-jose), role-based (super_admin/admin/user)
- **Container:** Docker on port 8000

## Project Structure
```
config/settings.py              — Sectors, thresholds, energy decision matrix
db/                             — SQLite database (empty on first run, auto-created)
utils/database.py               — 22 tables, WAL mode, auto-migration, init_db()
utils/auth.py                   — Legacy auth (roles, password hashing) — used by settings router
utils/ai_agent.py               — AI insights: morning briefing, KPI/table/site/executive analysis, DB-cached (6hr TTL)
utils/email_sender.py           — SMTP alerts, UI-configurable
utils/llm_client.py             — OpenRouter + Anthropic LLM client with fallback
parsers/blackout_parser.py      — Parses Blackout Hr_ Excel files (CFC, CMHL, CP, PG)
parsers/fuel_price_parser.py    — Parses Daily Fuel Price.xlsx (4 sheets, auto-detects old/new format)
parsers/name_normalizer.py      — Fixes generator name typos
parsers/sales_parser.py         — Parses daily + hourly sales (GOLD_CODE, CostCenter, SegmentName)
parsers/storemaster_parser.py   — Parses store master reference data
parsers/diesel_expense_parser.py — Parses LY diesel expense baseline (old 3-sheet or new single-sheet)
models/decision_engine.py       — Operating modes, delivery queue, budget, anomalies, transfers, load optimization
models/energy_cost.py           — Store economics: blackout-based buffer, date-specific pricing
models/fuel_price_forecast.py   — Ridge regression, 7-day price forecast
models/buffer_predictor.py      — Exponential smoothing, stockout projection
models/efficiency_scorer.py     — Isolation Forest anomaly detection
models/bcp_engine.py            — Weighted composite BCP scoring (A-F grades)
models/blackout_predictor.py    — GradientBoosting for blackout probability
agents/chat_agent.py            — Tool-calling AI chat with 15 tools, streaming progress
agents/tools/data_tools.py      — 9 query tools
agents/tools/model_tools.py     — 6 ML tools
agents/tools/registry.py        — Tool registry
alerts/alert_engine.py          — 11 alert conditions with escalation (incl. energy cost alerts)

backend/main.py                 — FastAPI app, CORS, router mounting, SPA serving
backend/routers/auth.py         — JWT login/logout, role guards (get_current_user, require_admin, require_super_admin)
backend/routers/data.py         — /upload/validate, fuel data endpoints
backend/routers/upload.py       — /upload (file import), /upload/clear, /upload/raw, /upload/history
backend/routers/charts.py       — /sector-heatmap, /sites-summary, chart data
backend/routers/insights.py     — /period-kpis, /yesterday-comparison, /sector-sites, /sector-snapshot
backend/routers/operations.py   — /operating-modes, /delivery-queue, /generator-risk, /transfers
backend/routers/ai.py           — /insights (AI), /chat/history, /ws/chat (WebSocket with streaming tool calls)
backend/routers/settings.py     — /users, /smtp, /recipients, /system/stats
backend/routers/export.py       — Excel export with merged headers, colored icons
backend/routers/config.py       — /config endpoints

frontend/src/routes/login/+page.svelte        — Login page
frontend/src/routes/dashboard/+page.svelte     — Main dashboard (Overview, Operations, Risk, Fuel, Predictions tabs)
frontend/src/routes/dashboard/+layout.svelte   — Auth guard + boot animation
frontend/src/routes/chat/+page.svelte          — AI chat with per-user history, streaming tool calls
frontend/src/routes/upload/+page.svelte        — Data upload with progress bars, validation, data quality
frontend/src/routes/settings/+page.svelte      — User management, SMTP, system stats
frontend/src/lib/api.ts                        — API client (BASE from env, auth headers, exported API_BASE)
frontend/src/lib/charts.ts                     — ECharts config builders
frontend/src/lib/stores/auth.ts                — Auth stores (user, isAuthenticated)
frontend/src/lib/components/AppHeader.svelte   — Top nav with role-based filtering
frontend/src/lib/components/Chart.svelte       — ECharts wrapper
frontend/src/lib/components/MiniChart.svelte   — Sparkline for KPI cards
frontend/src/lib/components/KpiCard.svelte     — KPI card component
frontend/src/lib/components/SiteModal.svelte   — Site detail modal
frontend/src/lib/components/AiInsightPanel.svelte — AI insight with auto-load, cache, refresh
frontend/src/lib/components/sections/          — Dashboard section components (SectorSites, SectorHeatmap, RiskPanel, FuelIntel, Predictions, OperatingModes, etc.)
```

## Key Patterns

### Svelte 5 Runes (CRITICAL):
- Use `$state`, `$derived`, `$effect`, `$props` — NOT legacy `$:` reactive declarations
- `{@const}` must be inside `{#if}`, `{#each}` blocks, NOT inside plain HTML elements
- HTML entities required in templates: `&lt;` `&gt;` `&divide;` `&times;` (not `<` `>` `/` `*`)

### API Client:
- All API calls use: `api.get('/endpoint')`, `api.post('/endpoint', data)`
- Base URL from env, auth headers attached automatically

### WebSocket Chat:
- Authenticated via `?token=JWT`
- Streams thinking/tool progress events
- Per-user chat history stored in `chat_messages` DB table

### AI Insights:
- Button-triggered (not auto-run) to control API costs
- Types: morning_briefing, kpi_insight, table_insight, site_insight, executive_analysis
- Gemini 3.1 Flash Lite via OpenRouter (~$0.004/analysis)
- DB-cached with 6-hour TTL in `ai_insights_cache` table + localStorage

### Upload:
- Excel validation uses openpyxl `read_only` metadata (no pandas) for instant validation
- Upload progress via `XMLHttpRequest.upload.onprogress`
- Full Replace Mode for ops data: clears daily_operations, site_summary, fuel_purchases, alerts, ai_cache, generators, sites
- Sales data uses upsert (append/update, not full replace)
- Supports: 4 blackout files (CFC, CMHL, CP, PG), 1 fuel price, 1 combo sales file, 1 LY diesel expense
- Auto-detects file type by Excel sheet names

### Parser (blackout_parser.py) — Important Behaviors:
- **Multi-generator same model:** Appends `-G2`, `-G3` suffixes to differentiate
- **Merged seq cells:** Checks static columns AND all date columns before skipping — row only skipped if ALL columns are empty
- **All columns use SUM:** gen_hr, fuel (daily_used), tank (spare_tank_balance), and blackout all use SUM aggregation
- **Time-formatted cells (h:mm):** Detected and converted to decimal hours (e.g. 5:30 = 5.5 hours)
- **Subtotal rows:** Formula rows (=SUM()) automatically detected and skipped
- **Empty future dates:** Date columns that are entirely empty are skipped — no zero rows generated
- **Tank on ALL generator rows:** Tank balance stored on every generator row (not deduplicated) — each row represents a separate drum/tank

### Date-specific fuel pricing:
- `_price_on_date(sector_id, date_str)` returns the most recent purchase price on or before that date
- NOT an average — uses the latest price at each point in time
- `_price_history` dict caches all purchase dates/prices per sector

### Database access:
```python
from utils.database import get_db
with get_db() as conn:
    df = pd.read_sql_query("SELECT ...", conn)
```

### Database (utils/database.py) — Key Behaviors:
- **refresh_site_summary:** ALL columns use SUM (gen_hr, fuel, tank, blackout) — each generator row represents a separate drum/tank
- **Clear data:** Deleting data also deletes generators + sites for clean re-upload

### Authentication:
- JWT tokens via python-jose
- Roles: super_admin > admin > user
- Guards: `get_current_user`, `require_admin`, `require_super_admin`
- Super admin credentials from env (SUPER_ADMIN_USER/PASS)

## Page Architecture

### Dashboard (frontend/src/routes/dashboard/+page.svelte):
Tabs: Overview, Operations, Risk, Fuel, Predictions

#### Overview Cockpit:
- **6 KPI Cards** — Gen Hours, Fuel Used, Tank Balance, Blackout Hours, Sales, Diesel Cost
  - Each card: Total value + Per Site value + horizontal bar sparkline (MiniChart.svelte)
  - Daily breakdown bars with 3-day average reference line
  - 1D (last day) vs 3D (avg) comparison in one unified layout
- **3 Derived KPI Cards** — Sales (1D/3D), Fuel Cost (1D/3D), Diesel% (1D/3D)
- **Situation Report** — Auto-generated narrative summary

#### Sector Heatmap:
- One row per sector with aggregated metrics
- Buffer = last day tank / 3-day avg fuel (NOT AVG of per-site buffer days)

#### Sector Sites (drill-down):
- Full site table with columns: SALES_1D, SALES_3D, SALES_AVG, COST_1D, COST_3D, COST_AVG, EXP%_1D, EXP%_3D, EXP%_TOTAL, MARGIN%_1D, MARGIN%_3D

#### Upload Page:
- DATA_QUALITY tab — compares Excel totals vs DB totals per date per sector
- Detects issues: time-formatted cells (h:mm), missing SUM formulas

### Filters:
- **Quick Filters** — Yesterday, 3D, 7D, 14D, 30D, 60D, All buttons
- **Date Range** — From/To date inputs with calendar filter
- **Site Type** — All / Regular / LNG dropdown
- All queries respect date filters; /period-kpis accepts `date_to` param

## Hierarchy from Excel data:
```
business_sector (from Excel) -> company (from Excel) -> site_id -> generator_id
Distribution                    PG                     PG-PGWH    PG-PGWH_100KVA
F&B                            CFC                    CFC-SBFTY  CFC-SBFTY_550 KVA-G1
Property                       CPPL, CMHL SC, UCC     CP-xxx     CP-xxx_model
Retail                         CMHL, MCS              CMHL-xxx   CMHL-xxx_model
```

## Sectors
- **CFC** (City Food Concepts): F&B sector, 2 sites
- **CMHL** (City Mart Holdings): Retail sector, 31 sites
- **CP** (City Properties): Property sector, 25 sites
- **PG** (PG Sector): Distribution sector, 2 sites

## Key Formulas
- **Buffer Days:** `last day tank / 3-day avg daily fuel` (sector level in /sector-heatmap)
- **Daily Burn:** `SUM(total_daily_used) / COUNT(DISTINCT dates)` (not SQL AVG)
- **Diesel Cost:** `Daily Used x Date-Specific Price` (latest purchase price on/before each date)
- **Diesel % of Sales:** `(Liters x Price) / Sales x 100`
- **Diesel Needed:** `SUM(7 x Avg Burn - Tank)` for sites below 7 days
- **Variance:** `Actual Used - (Rated L/hr x Run Hours)`
- **Efficiency:** `Liters Used / Gen Hours` (normal: flat; spike up = waste/theft)
- **Peak Hours:** `Avg Hourly Sales / Diesel Cost/Hr` (green>3x, yellow>1.5x, orange>1x, red<1x)
- **All KPIs:** SUM across all generator rows per site per date (gen_hr, fuel, tank, blackout)
- **Tank:** SUM of all generator rows — each row represents a separate drum/tank
- **Blackout:** SUM (filled on first row only per site per data entry instructions)
- **3D comparison:** daily averages (not sums) for fair comparison with 1-day values
- **Per Site:** total / number of distinct sites in period

## API Endpoints (key ones)

### /period-kpis
- Accepts `date_to` param, respects calendar filter
- Returns: `recent_daily` (last 4 days for sparklines), `story` (auto-generated narrative)
- Fields: `total_gen_hr`, `total_fuel`, `total_blackout`, `total_tank`, `tank_per_site`, `fuel_per_site`, `blackout_per_site`, `gen_hr_per_site`
- Uses `fmtN()` helper for narrative number formatting
- Uses `_sanitize()` helper to prevent NaN/Inf JSON serialization errors

### /sector-heatmap
- Buffer = last day tank / 3-day avg fuel (NOT AVG of per-site buffer days)
- One row per sector with aggregated metrics

### /sector-sites
- Site-level drill-down with columns: `last_day_sales`, `avg3d_sales`, `last_day_fuel_cost`, `avg3d_fuel_cost`, `exp_pct_last_day`, `exp_pct_3d`, `exp_pct_total`, `margin_pct_last_day`, `margin_pct_3d`

### /upload/validation
- Compares DB totals vs Excel totals per date per sector
- Detects issues: time-formatted cells (h:mm), missing SUM formulas

## Environment Variables
```
OPENROUTER_API_KEY    — Required for AI features (Gemini 3.1 Flash Lite)
JWT_SECRET            — Required in Docker (raises error if missing)
SUPER_ADMIN_USER      — Default: admin
SUPER_ADMIN_PASS      — Default: admin123
CORS_ORIGINS          — Default: localhost:3000,5173,8000
DATA_DIR              — Default: ./db
```

## Docker
```bash
docker-compose up -d --build     # Build and run on port 8000
docker-compose down              # Stop
docker-compose down -v           # Stop + delete DB volume (full reset)
```
