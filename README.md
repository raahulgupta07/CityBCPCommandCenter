# CityBCPAgent

AI-powered Business Continuity Planning dashboard for managing backup generators, fuel supply, and sales-vs-energy profitability across 55+ sites in Myanmar during power outages and diesel shortages.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.50-red) ![Claude](https://img.shields.io/badge/AI-Claude%20Haiku%204.5-purple) ![Docker](https://img.shields.io/badge/Docker-Ready-green)

## The Problem

Myanmar faces frequent power outages. Organizations with 55+ outlets need to decide daily:
- **Which outlets can operate?** (full, reduced, generator-only, or close)
- **Where should the fuel truck go first?** (prioritized by urgency)
- **Is the energy cost justified by sales revenue?** (profitability check)
- **How much will fuel cost this week?** (budget planning)
- **Which generators need maintenance?** (prevent failures during crisis)

## The Solution

A single dashboard that answers all these questions with AI-powered analysis. Database starts empty — upload your own Excel data via the Data Entry page.

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

### Sales vs Energy Analysis (Page 12)
| Feature | What It Does |
|---|---|
| Energy % of Sales | Core KPI — energy cost as percentage of revenue per sector |
| Sector Comparison | CP vs CMHL vs CFC side-by-side bars and tables |
| Energy Deep Dive | All BCP sites sorted by energy cost, expandable per-generator detail |
| Sales Deep Dive | Top revenue and margin sites from POS data |
| Hourly Analysis | Peak sales hours vs generator run hours |
| Store Decision | Colored recommendation cards: FULL/MONITOR/REDUCE/CLOSE per sector |
| Daily Trend | Energy cost % over time with threshold lines |

### 13 Dashboard Pages
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
11. **Settings** — email configuration, user management
12. **Data Quality** — automated spec validation, reporting gaps, anomaly detection
13. **Sales vs Energy** — energy expense vs sales revenue profitability

### 5 ML Models
| Model | Algorithm | Purpose |
|---|---|---|
| Fuel Price Forecast | Ridge Regression | 7-day price prediction |
| Buffer Depletion | Exponential Smoothing | When will sites run out |
| Efficiency Scorer | Isolation Forest | Generator anomaly detection |
| BCP Score Engine | Weighted Composite | Site risk grades A-F |
| Blackout Predictor | Gradient Boosting | Blackout probability |

### AI Agent (Claude Haiku 4.5)
- 15 tools for querying data, running models, comparing energy vs sales
- Natural language: "Which sites have less than 3 days of fuel?"
- Sales queries: "Compare energy cost vs sales for CP sector"
- Deep analysis: sends full chart/table data to LLM
- Each insight shows calculation method + data source

### Authentication & Roles
| Role | Access |
|---|---|
| Super Admin | Everything — settings, users, upload, analysis |
| Admin | Upload data, run analysis, manage recipients |
| User | View dashboards only (read-only) |

### Email Alerts (11 types)
- Auto-sends after data upload when critical thresholds are breached
- Includes energy cost alerts (when energy > 15% or 30% of sales)
- Pre-configured for Gmail, Outlook, Office 365, Yahoo, SendGrid, Zoho, Amazon SES
- Per-recipient severity + sector filters
- SMTP configured via UI (no .env editing needed)

## Quick Start

### Docker (recommended)
```bash
git clone https://github.com/raahulgupta07/CityBCPAgent.git
cd CityBCPAgent/CityBCPAgentv1
cp .env.example .env
# Edit .env with your OpenRouter API key and super admin credentials
docker compose up -d --build
# Open http://localhost:8501
# Login: admin / admin123 (change in .env before first run)
# Upload your data via Data Entry page
```

### Local Development
```bash
git clone https://github.com/raahulgupta07/CityBCPAgent.git
cd CityBCPAgent/CityBCPAgentv1
pip install -r requirements.txt
cp .env.example .env
# Edit .env
streamlit run app.py
# Upload your data via Data Entry page
```

## Data Input

Database starts **empty** — upload your Excel files via the Data Entry page. The system auto-detects file types by reading sheet names inside each file. File names don't matter.

### Supported File Types (up to 7 files)
| File | Sheet Name(s) | Purpose |
|---|---|---|
| Blackout Hr_ CP.xlsx | `CP` | City Pharmacy generator + fuel data |
| Blackout Hr_ CMHL.xlsx | `CMHL` | City Mart Holdings generator + fuel data |
| Blackout Hr_ CFC.xlsx | `CFC` | City Food Concepts generator + fuel data |
| Daily Fuel Price.xlsx | `CMHL, CP, CFC, PG` | Fuel purchase prices per sector |
| daily sales data.xlsx | `daily sales` | Daily sales per site per brand |
| hourly sales data.xlsx | `hourly sales` | Hourly sales with transaction counts |
| storemaster.xlsx | `STORE MASTER` | Store reference data (segment, location, size) |

### What the parser handles automatically:
- Generator name typos (KHOLER→KOHLER, HIMONISA→HIMOINSA)
- Dynamic columns (new days = new columns, auto-detected)
- Dashes, blanks, #DIV/0!, text notes → cleaned to NULL
- Multi-generator sites → aggregated correctly
- Validation: rejects gen hours > 24, keeps rest of data
- Brand→Sector mapping for sales data (auto-resolved)
- Store segment→sector mapping from storemaster

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
├── config/settings.py          # All configuration, thresholds, brand/sector maps
├── db/                         # SQLite database (empty on first run)
├── utils/
│   ├── database.py             # 19 tables, WAL mode, CRUD
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
│   ├── name_normalizer.py      # Generator name typo fixing
│   ├── sales_parser.py         # Daily + hourly sales parser
│   └── storemaster_parser.py   # Store master reference parser
├── models/
│   ├── decision_engine.py      # 15 Tier 1-3 predictions + energy awareness
│   ├── energy_cost.py          # Energy vs sales: breakdown, decision matrix
│   ├── fuel_price_forecast.py  # Ridge regression, 7-day forecast
│   ├── buffer_predictor.py     # Exponential smoothing, stockout
│   ├── efficiency_scorer.py    # Isolation Forest anomalies
│   ├── bcp_engine.py           # Weighted composite BCP scores
│   └── blackout_predictor.py   # Gradient Boosting classifier
├── agents/
│   ├── chat_agent.py           # Tool-calling AI chat
│   └── tools/                  # 15 registered tools (9 data + 6 ML)
├── alerts/
│   └── alert_engine.py         # 11 alert conditions (incl. energy cost)
├── pages/                      # 13 dashboard pages (00-12)
├── Dockerfile
├── compose.yaml
└── seed_database.py            # One-time seed script (optional, for dev)
```

## Database Schema (19 tables)

| Table | Purpose |
|---|---|
| users | Authentication + roles |
| sessions | Persistent login tokens |
| sectors | CP, CMHL, CFC, PG |
| sites | Outlet locations |
| generators | Generator models per site |
| daily_operations | Per-generator per-day fact table |
| daily_site_summary | Aggregated: buffer days, totals |
| fuel_purchases | Diesel prices from suppliers |
| store_master | Sales system store reference (segment, location) |
| daily_sales | Daily sales per site per brand |
| hourly_sales | Hourly sales with transaction counts |
| site_sales_map | Optional: maps sales sites to BCP sites |
| alerts | Auto-generated threshold alerts |
| alert_recipients | Email notification targets |
| email_log | Delivery audit trail |
| app_settings | SMTP config, preferences |
| ai_insights_cache | Persisted AI analysis |
| upload_history | File import audit |
| generator_name_map | Typo → canonical name mapping |

## Energy Cost Thresholds

| Energy % of Sales | Status | Recommendation |
|---|---|---|
| < 5% | HEALTHY | Full operations |
| 5-15% | MONITOR | Review generator schedules |
| 15-30% | REDUCE | Cut generator hours by 20% |
| 30-60% | CRITICAL | Essential hours only |
| > 60% | CLOSE | Temporary closure recommended |

## License

Private project for City Holdings Myanmar.
