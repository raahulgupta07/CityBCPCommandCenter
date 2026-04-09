# CityBCPAgent v2 -- BCP Command Center

AI-powered Business Continuity Planning dashboard for managing backup generators, fuel supply, and sales-vs-energy profitability across 60+ sites in Myanmar.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![SvelteKit](https://img.shields.io/badge/SvelteKit%205-Frontend-FF3E00)
![Gemini AI](https://img.shields.io/badge/AI-Gemini%203.1%20Flash%20Lite-purple)
![Docker](https://img.shields.io/badge/Docker-Ready-green)

---

## The Problem

Myanmar faces frequent power outages. Organizations with 60+ outlets need to answer critical questions every day:

- **Which outlets can operate?** Full, reduced, generator-only, or close.
- **Where should the fuel truck go first?** Prioritized by urgency and buffer days.
- **Is the energy cost justified by sales revenue?** Profitability check per site.
- **Which hours should each store be open?** Peak hours analysis.
- **How much will fuel cost this week?** Budget planning and forecasting.
- **Is there fuel theft?** Anomaly detection on consumption patterns.

## The Solution

A single **BCP Command Center** dashboard that answers all questions with drill-down hierarchy:

```
Group (all 60+ sites)
  |-- Distribution (PG) -- PG -- [PG-PGWH, PG-PGMDY]
  |-- F&B (CFC) -- CFC -- [CFC-SBFTY, CFC-BMDY]
  |-- Property (CP) -- CPPL, CMHL SC, UCC -- [25 sites]
  |-- Retail (CMHL) -- CMHL, MCS -- [31 sites]
```

**4 Sectors:** CFC, CMHL, CP, PG

The database starts empty. Upload your own Excel data via the UI and the dashboard populates automatically.

---

## Features

### Dashboard Tabs

| Tab | Purpose |
|---|---|
| **Overview** | 2-column layout: KPI cards with sparklines (left), AI insights panel (right), situation report, sector heatmap |
| **Operations** | Operating modes, delivery queue, generator fleet status |
| **Risk** | 4-chapter panel: Stockout Forecast, BCP Risk Grades (A-F), Active Alerts, Break-Even Analysis |
| **Fuel & Cost** | Fuel trends, diesel cost vs sales, expense percentages |
| **Predictions** | 15 forecasts: fuel consumption, buffer depletion, price alerts, theft probability |

### KPI Cards with Sparklines

Six core metrics -- Gen Hours, Fuel Used, Tank Balance, Blackout Hours, Sales, Diesel Cost -- each with:
- Total value and per-site breakdown
- Horizontal bar sparklines (last 4 days)
- 1-day vs 3-day average comparison
- InfoTip button on every card -- click to see the exact formula and explanation behind each metric

### InfoTip System

Every KPI card and chart includes a clickable info icon that reveals:
- The formula used to calculate the metric
- A plain-English explanation of what the number means
- Thresholds and color-coding logic where applicable

### Sector Heatmap and Site Drill-Down

- One row per sector with aggregated metrics and color-coded status icons
- Click any sector to drill down into individual site data (Site Deep Dive modal)
- Columns include sales, fuel cost, expense %, and margin % (1-day, 3-day, and total)

### AI Executive Briefing

McKinsey-style situation report generated on demand:
- URGENT / WATCH / POSITIVE summary with specific site names and actions
- Powered by Gemini 3.1 Flash Lite via OpenRouter
- Button-triggered (not auto-run), cached in DB with 6-hour TTL
- Displayed in the right column of the 2-column Overview layout

### AI Chat with Inline Charts and Tables

- 15 tools: 9 data query tools + 6 ML model tools
- Streaming tool call progress (shows each tool as it runs)
- **Inline ECharts** rendered directly in chat responses (bar, line, pie charts)
- **Formatted tables** with color-coded cells in chat output
- GPT-style clickable example questions to get started quickly
- Per-user chat history stored in database
- Natural language queries: "Which sites are critical?", "Forecast fuel for next week"
- **Filter-aware insights** -- detects when dashboard filters change and prompts the user to refresh AI analysis

### Monte Carlo Stockout Simulation

- 1,000 simulations per site to estimate days until fuel stockout
- Results presented as P10 / P50 / P90 confidence intervals (pessimistic / median / optimistic)
- Drives the Stockout Forecast chapter in the Risk panel

### Custom BCP Command Center Favicon

Custom branded favicon for browser tabs and bookmarks.

### Data Upload

- Drag-and-drop Excel upload with progress bars
- Auto-detects file type by sheet names
- DATA_QUALITY validation tab: compares Excel totals vs DB totals per date per sector
- DIFF columns (GEN HR, FUEL, TANK, BLACKOUT) show the exact difference between Excel and DB values per date per sector
- Results cached in `excel_validation_cache` table for instant re-display
- Detects time-formatted cells, missing SUM formulas, and other issues

### Excel Export

- Merged headers with colored status icons
- Heatmap thresholds for buffer days, diesel price, blackout hours, expense %

### Role-Based Access Control

| Role | Permissions |
|---|---|
| **super_admin** | Full access, user management, settings |
| **admin** | Dashboard, upload, chat, export |
| **user** | Dashboard view only |

### CP Center Diesel Allocation

CMHL stores inside CP shopping centers get diesel cost allocated from center generators:
- 17 stores auto-detected using 4-check logic (UNKNOWN model + zero fuel + no spec + 1 generator)
- Separate `CP_CENTER_ALLOCATION` table with: CENTER, ALLOC%, shared blackout/gen hours, allocated tank/fuel/cost
- CP CENTER RAW validation columns for verification
- LY BASELINE columns (last year cost/day and diesel %) for comparison

### Risk Panel (4 Chapters)

Rebuilt risk assessment with scrollable tables and auto-generated situation report:
- **Stockout Forecast** -- Sites sorted by urgency with colored days-left indicators, trend arrows, confidence levels
- **BCP Risk Grades** -- Grade distribution (A through F), composite scores with fuel/coverage/power/resilience breakdown
- **Active Alerts** -- Severity breakdown (CRITICAL/WARNING/INFO), alert type badges, searchable alert table
- **Break-Even Analysis** -- Avg fuel/day vs avg sales, diesel % with color thresholds
- Formula reference section for full transparency
- Excel export per chapter

### Site Type Filter

- ALL / REGULAR / LNG filter works across every dashboard tab
- 16 frontend components and 20 backend endpoints support `site_type` parameter

### Boot Sequence Animation

Animated startup sequence on first load for a polished launch experience.

---

## Quick Start (Docker)

```bash
git clone https://github.com/raahulgupta07/cityagenticbcp.git
cd cityagenticbcp
docker-compose up -d --build
# Open http://localhost:8000
# Login: admin / admin123
# Upload data via DATA_ENTRY page
# Optional: add OPENROUTER_API_KEY to .env for AI features
```

**Zero-config install:** JWT_SECRET auto-generates on first run (persisted in db volume). No `.env` setup required for basic usage -- only add `OPENROUTER_API_KEY` if you want AI features.

## Local Development

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | No | -- | API key for Gemini AI features (only needed for AI) |
| `SUPER_ADMIN_USER` | No | `admin` | Super admin username |
| `SUPER_ADMIN_PASS` | No | `admin123` | Super admin password |
| `SUPER_ADMIN_EMAIL` | No | -- | Super admin email |
| `JWT_SECRET` | No | auto-generated | Auto-generates and persists to `db/.jwt_secret` if not set |
| `CORS_ORIGINS` | No | `localhost:3000,5173,8000` | Allowed CORS origins |
| `DATA_DIR` | No | `./db` | SQLite database directory |
| `BCP_AGENT_ENABLED` | No | `true` | Enable/disable AI chat agent |

---

## Data Input

Database starts **empty**. Upload Excel files via the Upload page. The system auto-detects file type by sheet names.

| File | Sheets | Purpose |
|---|---|---|
| Blackout Hr_ CFC.xlsx | `CFC` | CFC generators + fuel + blackout hours |
| Blackout Hr_ CMHL.xlsx | `CMHL` | CMHL generators + fuel + blackout hours |
| Blackout Hr_ CP.xlsx | `CP` | CP generators + fuel + blackout hours |
| Blackout Hr_ PG.xlsx | `PG` | PG generators + fuel + blackout hours |
| Daily Fuel Price.xlsx | `CMHL, CP, CFC, PG` | Fuel purchase prices per supplier |
| CMHL_DAILY_SALES.xlsx | `daily sales, hourly sales, STORE MASTER` | Sales revenue + store master |
| Diesel Expense LY.xlsx | -- | Last year diesel expense baseline |

### Excel Column Reference (Blackout Hr files)

| Column | Description | Used In |
|---|---|---|
| Gen Run Hr | Hours generator ran that day | Efficiency, gen hours charts |
| Daily Used | Liters of diesel used/refilled | Fuel burn, cost, buffer calculations |
| Spare Tank Balance | Closing fuel balance in tank (liters) | Buffer days, tank charts |
| Consumption Per Hour | Generator rated L/hr capacity | Buffer calculation, variance |
| Blackout Hr | Hours of power outage | Buffer, blackout charts |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | SvelteKit 5 (Svelte 5 runes) + adapter-static (SPA) + ECharts + TailwindCSS 4 |
| Backend | FastAPI (Python 3.12) + SQLite (WAL mode, 24 tables, auto-migration) |
| ML | scikit-learn (Ridge, GradientBoosting, Isolation Forest), AR(3) via LinearRegression, numpy Monte Carlo |
| AI | Gemini 3.1 Flash Lite via OpenRouter (google/gemini-3.1-flash-lite-preview) |
| Auth | JWT session tokens (python-jose), role-based access (super_admin / admin / user) |
| Container | Docker on port 8000 |

---

## ML Models

| Model | Method | Purpose |
|---|---|---|
| Ridge Regression | Price forecast | 7-day fuel price prediction (linear trend) |
| GradientBoosting | Price forecast | Non-linear fuel price patterns |
| Ensemble | Price forecast | Average of Ridge + GBR for robust predictions |
| EMA | Buffer forecast | Exponential smoothing for fuel consumption trends |
| AR(3) | Fuel forecast | Autoregressive 3-day lag model for consumption forecasting |
| Monte Carlo | Stockout simulation | 1,000 simulations per site producing P10/P50/P90 confidence intervals |
| Isolation Forest | Anomaly detection | Flags fuel waste or theft based on consumption patterns |
| GradientBoosting | Blackout prediction | Tomorrow's blackout probability based on historical patterns |
| Weighted Composite | BCP scoring | A-F grades (Fuel 35% + Coverage 30% + Power 20% + Resilience 15%) |

---

## Key Calculations

| Metric | Formula | Note |
|---|---|---|
| Buffer Days | Last day tank / 3-day avg daily fuel | Sector-level in heatmap |
| All KPIs | SUM across all generator rows per site per date | gen_hr, fuel, tank, blackout all use SUM |
| Tank | SUM of all generator rows | Each row = separate drum/tank |
| Daily Burn | SUM(Daily Used) / COUNT(days) | Not SQL AVG |
| Diesel Cost | Daily Used x Date-Specific Price | Latest purchase price on each date |
| Diesel % | (Liters x Price) / Sales x 100 | <0.9% good, <1.5% watch, <3% warning, >3% danger |
| Efficiency | Liters / Gen Hours (L/Hr) | Flat = normal, spike = waste/theft |
| Variance | Actual Used - (Rated L/Hr x Run Hours) | Positive = overconsumption |
| 3D Comparison | Daily averages (not sums) | Fair comparison with 1-day values |
| Allocated Blackout | CP center blackout (100% shared) | Same power outage for entire mall |
| Allocated Tank | CP center tank x allocation % | Store's share of fuel reserve |
| Allocated Fuel | CP center fuel x allocation % | Store's share of diesel consumed |
| Allocated Cost | Allocated fuel x CP price | What CP charges the store |
| Auto-Detection | UNKNOWN model + 0 fuel + 0 L/hr + 1 gen | Identifies stores needing allocation |

---

## Project Structure

```
backend/
  main.py                       -- FastAPI app entry point
  routers/
    auth.py                     -- Login/logout/session endpoints
    upload.py                   -- File upload + validation
    data.py                     -- KPIs, heatmap, site drill-down
    charts.py                   -- Chart data endpoints
    ai.py                       -- AI insight endpoints
    operations.py               -- Operations endpoints
    export.py                   -- Excel export endpoints
    settings.py                 -- Settings endpoints
frontend/
  src/
    routes/                     -- Pages: dashboard, upload, chat, login, settings
    lib/
      components/               -- KpiCard, MiniChart, Chart, DatePicker, SiteModal, etc.
      components/sections/      -- 16 dashboard panels (RiskPanel, SectorSites, FuelIntel, etc.)
      stores/                   -- Svelte stores (state management)
      api.ts                    -- API client
      charts.ts                 -- Chart config helpers
config/
  settings.py                   -- Sectors, thresholds, mappings
parsers/                        -- Excel file parsers (blackout, fuel, sales, expense)
models/                         -- Decision engine, energy cost, predictions, BCP scoring
agents/
  chat_agent.py                 -- Tool-calling AI chat with 15 tools
  tools/                        -- data_tools.py (9 query tools), model_tools.py (6 ML tools)
alerts/
  alert_engine.py               -- 11 alert conditions with escalation
utils/                          -- Database, auth, AI, charts, tables, KPI helpers
db/                             -- SQLite database (created on first run)
```

---

## AI Features

### Executive Briefing

Four insight types generated on demand:
- **Morning Briefing** -- URGENT / WATCH / POSITIVE summary with specific site names
- **KPI Analysis** -- Interpretation of what current KPIs mean for operations
- **Table Analysis** -- Which sector needs attention and why
- **Site Analysis** -- Deep-dive on buffer, efficiency, cost vs sales, recommendation

Cost: approximately $0.004 per analysis via OpenRouter.

### Chat Agent

Natural language interface with 15 tools:

| Category | Tools | Examples |
|---|---|---|
| Data Queries (9) | Site status, fuel levels, sales, blackout hours, etc. | "Show me all critical sites" |
| ML Models (6) | Fuel forecast, anomaly detection, buffer prediction, etc. | "Predict fuel consumption for next week" |

- Streaming responses with tool-calling chains and per-user conversation history
- Inline ECharts (bar, line, pie) rendered directly in chat messages
- Formatted markdown tables with color-coded cells
- GPT-style clickable example questions for quick onboarding
- Filter-aware: detects dashboard filter changes and prompts insight refresh

---

## Screenshots

Key views in the application:

- **Overview Dashboard** -- 2-column layout with KPI cards and sparklines on the left, AI insights panel on the right
- **AI Chat** -- Conversational interface with inline ECharts, formatted tables, and clickable example questions
- **Site Deep Dive Modal** -- Drill-down into individual site metrics, generator details, and efficiency analysis
- **What's Next (Predictions)** -- 15 ML forecasts including fuel consumption, buffer depletion, price alerts, and theft probability

---

## Docker Commands

```bash
docker-compose up -d --build     # Build and run
docker-compose down              # Stop
docker-compose down -v           # Stop + delete DB volume (full reset)
docker logs city-bcp-agent       # View logs
```

---

## License

Private project for City Holdings Myanmar.
