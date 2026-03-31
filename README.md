# 🛡️ CityBCPAgent

AI-powered Business Continuity Planning dashboard for managing backup generators and fuel supply across 55+ sites in Myanmar during power outages and diesel shortages.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.50-red) ![Claude](https://img.shields.io/badge/AI-Claude%20Haiku%204.5-purple) ![Docker](https://img.shields.io/badge/Docker-Ready-green)

## The Problem

Myanmar faces frequent power outages. Organizations with 55+ outlets need to decide daily:
- **Which outlets can operate?** (full, reduced, generator-only, or close)
- **Where should the fuel truck go first?** (prioritized by urgency)
- **How much will fuel cost this week?** (budget planning)
- **Which generators need maintenance?** (prevent failures during crisis)

## The Solution

A single dashboard that answers all these questions with AI-powered analysis.

## Features

### Daily Decision Board (the #1 page)
| Feature | What It Does |
|---|---|
| Operating Mode | Recommends FULL/REDUCED/GEN-ONLY/CLOSE per site |
| Delivery Queue | Prioritized list with exact liters, deadline, cost |
| Cost Calculator | Cost per hour per generator, weekly budget forecast |
| Supplier Signal | BUY NOW / WAIT / HOLD based on price trends |
| Maintenance Alerts | Generator failure risk based on cumulative run hours |
| Anomaly Detection | Sites using 30%+ more fuel than normal |
| Resource Sharing | Transfer excess fuel between sectors |
| Load Optimization | Which generator to run at multi-gen sites |
| Recovery Estimate | How fast sites restart after grid power returns |
| What-If Simulator | "What if diesel hits 10,000 MMK?" |

### 10 Dashboard Pages
1. **Decision Board** — daily operating decisions
2. **Sector Overview** — compare CP vs CMHL vs CFC
3. **Site Detail** — drill into any site's generators
4. **Fuel Price** — price trends, supplier comparison, 7-day forecast
5. **Buffer Risk** — stockout predictions, critical sites
6. **Power Backup** — generator run hours as blackout proxy
7. **Generator Fleet** — efficiency scoring, anomalies
8. **BCP Command Center** — complete risk overview with scores A-F
9. **AI Insights** — chat agent, deep analysis, alerts
10. **Data Entry** — upload Excel files, browse raw data

### 5 ML Models
| Model | Algorithm | Purpose |
|---|---|---|
| Fuel Price Forecast | Ridge Regression | 7-day price prediction |
| Buffer Depletion | Exponential Smoothing | When will sites run out |
| Efficiency Scorer | Isolation Forest | Generator anomaly detection |
| BCP Score Engine | Weighted Composite | Site risk grades A-F |
| Blackout Predictor | Gradient Boosting | Blackout probability |

### AI Agent (Claude Haiku 4.5)
- 12 tools for querying data, running models, generating forecasts
- Natural language: "Which sites have less than 3 days of fuel?"
- Deep analysis: sends full chart/table data to LLM
- Each insight shows calculation method + data source

### Authentication & Roles
| Role | Access |
|---|---|
| Super Admin | Everything — settings, users, upload, analysis |
| Admin | Upload data, run analysis, manage recipients |
| User | View dashboards only (read-only) |

### Email Alerts
- Auto-sends after data upload when critical thresholds are breached
- Pre-configured for Gmail, Outlook, Office 365, Yahoo, SendGrid, Zoho, Amazon SES
- Per-recipient severity + sector filters
- SMTP configured via UI (no .env editing needed)

## Quick Start

### Docker (recommended)
```bash
git clone https://github.com/raahulgupta07/CityBCPAgent.git
cd CityBCPAgent
cp .env.example .env
# Edit .env with your OpenRouter API key and super admin credentials
docker compose up -d --build
# Open http://localhost:8501
# Login: admin / admin123 (change in .env before first run)
```

### Local Development
```bash
git clone https://github.com/raahulgupta07/CityBCPAgent.git
cd CityBCPAgent
pip install -r requirements.txt
cp .env.example .env
# Edit .env
streamlit run app.py
```

## Data Input

Upload the same Excel files your field teams already fill:
- `Blackout Hr_ CP.xlsx` — City Pharmacy (25 sites)
- `Blackout Hr_ CMHL.xlsx` — City Mart Holdings (30 sites)
- `Blackout Hr_ CFC.xlsx` — City Food Chain (2 factories)
- `Daily Fuel Price.xlsx` — Fuel purchase prices

**File names don't matter** — detection is by sheet names inside the Excel.

**Full Replace Mode** — each upload clears old data and replaces with new. Dashboard always shows the latest weekly data.

### What the parser handles automatically:
- Generator name typos (KHOLER→KOHLER, HIMONISA→HIMOINSA)
- Dynamic columns (new days = new columns, auto-detected)
- Dashes, blanks, #DIV/0!, text notes → cleaned to NULL
- Multi-generator sites → aggregated correctly
- Validation: rejects gen hours > 24, keeps rest of data

## Environment Variables

```env
# Required for AI features
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Super Admin (created on first run only)
SUPER_ADMIN_USER=admin
SUPER_ADMIN_PASS=change-this-password
SUPER_ADMIN_EMAIL=admin@company.com
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + streamlit-shadcn-ui + Plotly |
| Database | SQLite (WAL mode) |
| ML | scikit-learn (Ridge, Isolation Forest, Gradient Boosting) |
| AI | Claude Haiku 4.5 via OpenRouter |
| Auth | Session tokens in DB + URL params |
| Email | SMTP (configurable via UI) |
| Container | Docker |

## Project Structure

```
├── app.py                      # Home page
├── config/settings.py          # All configuration
├── db/bcp.db                   # Pre-seeded SQLite database
├── Data/                       # Excel source files (5 files)
├── utils/
│   ├── database.py             # 15 tables, WAL mode, CRUD
│   ├── auth.py                 # Login, roles, persistent sessions
│   ├── ai_insights.py          # Deep AI analysis, DB-cached
│   ├── llm_client.py           # OpenRouter + Anthropic client
│   ├── email_sender.py         # SMTP email alerts
│   ├── charts.py               # 12 Plotly chart builders
│   ├── smart_table.py          # HTML tables with severity badges
│   ├── kpi_card.py             # KPI cards with calculation transparency
│   └── page_header.py          # Consistent gradient headers
├── parsers/
│   ├── blackout_parser.py      # Dynamic Excel column detection
│   ├── fuel_price_parser.py    # 4-sheet price parser
│   └── name_normalizer.py      # Generator name typo fixing
├── models/
│   ├── decision_engine.py      # 15 Tier 1-3 predictions
│   ├── fuel_price_forecast.py  # Ridge regression, 7-day forecast
│   ├── buffer_predictor.py     # Exponential smoothing, stockout
│   ├── efficiency_scorer.py    # Isolation Forest anomalies
│   ├── bcp_engine.py           # Weighted composite BCP scores
│   └── blackout_predictor.py   # Gradient Boosting classifier
├── agents/
│   ├── chat_agent.py           # Tool-calling AI chat
│   └── tools/                  # 12 registered tools
├── alerts/
│   └── alert_engine.py         # 10 alert conditions
├── pages/                      # 11 dashboard pages
├── Dockerfile
├── compose.yaml
└── seed_database.py            # One-time Excel → DB migration
```

## Database Schema (15 tables)

| Table | Purpose |
|---|---|
| users | Authentication + roles |
| sessions | Persistent login tokens |
| sectors | CP, CMHL, CFC, PG |
| sites | 57 locations |
| generators | 86 generator models |
| daily_operations | Per-generator per-day fact table |
| daily_site_summary | Aggregated: buffer days, totals |
| fuel_purchases | Diesel prices from suppliers |
| alerts | Auto-generated threshold alerts |
| alert_recipients | Email notification targets |
| email_log | Delivery audit trail |
| app_settings | SMTP config, preferences |
| ai_insights_cache | Persisted AI analysis |
| upload_history | File import audit |
| generator_name_map | Typo → canonical name mapping |

## License

Private project for City Holdings Myanmar.
