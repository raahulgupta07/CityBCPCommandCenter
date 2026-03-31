# CLAUDE.md — Project Guide for AI Assistants

## What is this project?

CityBCPAgent is a Business Continuity Planning dashboard for managing backup generators and fuel supply across 55+ sites in Myanmar. It helps decision-makers during power outages and diesel shortages.

## Tech Stack
- **Frontend:** Streamlit 1.50 + streamlit-shadcn-ui 0.1.19 + Plotly
- **Database:** SQLite with WAL mode (db/bcp.db)
- **ML:** scikit-learn (Ridge, Isolation Forest, GradientBoosting)
- **AI:** Claude Haiku 4.5 via OpenRouter (cheapest Claude model)
- **Auth:** Session tokens stored in DB + URL query params
- **Container:** Docker on port 8501

## Project Structure
```
app.py                  — Home page (requires login)
config/settings.py      — Sectors, thresholds, colors, agent config
db/bcp.db               — SQLite database (committed to git, pre-seeded)
Data/                   — 5 Excel source files
utils/database.py       — 15 tables, WAL mode, all CRUD helpers
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
models/decision_engine.py   — 15 Tier 1-3 predictions (operating modes, delivery queue, costs, etc.)
models/fuel_price_forecast.py — Ridge regression, 7-day price forecast
models/buffer_predictor.py   — Exponential smoothing, stockout projection
models/efficiency_scorer.py  — Isolation Forest anomaly detection
models/bcp_engine.py        — Weighted composite BCP scoring (A-F grades)
models/blackout_predictor.py — GradientBoosting for blackout probability
agents/chat_agent.py    — Tool-calling AI chat with 12 tools
agents/tools/           — data_tools.py (6 query tools), model_tools.py (6 ML tools)
alerts/alert_engine.py  — 10 alert conditions with escalation
pages/00-10             — 11 Streamlit pages
seed_database.py        — One-time Excel → SQLite migration
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
- Full Replace Mode: clears daily_operations, site_summary, fuel_purchases, alerts, ai_cache
- Keeps: sites, generators, users, settings (structural data)
- Auto-detects file type by Excel sheet names (not filename)
- Auto-runs alerts after import
- Auto-sends email if SMTP configured

## Sectors
- **CP** (City Pharmacy): 25 sites, has blackout data
- **CMHL** (City Mart Holdings): 30 sites, no blackout tracking
- **CFC** (City Food Chain): 2 factories, has blackout tracking but all NULL
- **PG**: No active data

## Data Flow
```
Excel files → Parser (clean/validate) → SQLite DB → Dashboard pages
                                                   → ML Models → Predictions
                                                   → AI Agent → Deep insights
                                                   → Alert Engine → Email alerts
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

## Environment Variables
```
OPENROUTER_API_KEY    — Required for AI features
SUPER_ADMIN_USER      — Default: admin
SUPER_ADMIN_PASS      — Default: admin123
SUPER_ADMIN_EMAIL     — Optional
```

## Docker
```bash
docker compose up -d --build     # Build and run
docker compose down              # Stop
docker compose down -v           # Stop + delete DB volume
docker logs city-bcp-agent       # View logs
docker exec city-bcp-agent python3 -c "..."  # Run commands inside
```
