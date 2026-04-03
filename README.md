# CityBCPAgent — BCP Command Center

AI-powered Business Continuity Planning dashboard for managing backup generators, fuel supply, and sales-vs-energy profitability across 60+ sites in Myanmar during power outages and diesel shortages.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.50-red) ![Claude](https://img.shields.io/badge/AI-Claude%20Haiku%204.5-purple) ![Docker](https://img.shields.io/badge/Docker-Ready-green)

## The Problem

Myanmar faces frequent power outages. Organizations with 60+ outlets need to decide daily:
- **Which outlets can operate?** (full, reduced, generator-only, or close)
- **Where should the fuel truck go first?** (prioritized by urgency)
- **Is the energy cost justified by sales revenue?** (profitability check)
- **Which hours should each store be open?** (peak hours analysis)
- **How much will fuel cost this week?** (budget planning)
- **Is there fuel theft?** (anomaly detection)

## The Solution

A single **BCP Command Center** dashboard that answers all questions with drill-down hierarchy: **Group > Sector > Company > Site**. Database starts empty -- upload your own Excel data via the Data Entry page.

## Dashboard Pages (4 total)

| Page | Purpose |
|---|---|
| **BCP Command Center** | THE main page: all KPIs, 68 charts, 15 predictions, heatmaps, operations |
| **BCP Chat** | AI chat agent with 15 tools for natural language queries |
| **Data Entry** | Upload Excel files (CFC, CMHL, CP, PG blackout + fuel + sales) |
| **Settings** | User management, SMTP email config |

## BCP Command Center Features

### Hierarchy: Group > Sector > Company > Site
```
Group (all 60 sites)
  |-- Distribution (PG) ── PG ── [PG-PGWH, PG-PGMDY]
  |-- F&B (CFC) ── CFC ── [CFC-SBFTY, CFC-BMDY]
  |-- Property (CP) ── CPPL, CMHL SC, UCC ── [25 sites]
  |-- Retail (CMHL) ── CMHL, MCS ── [31 sites]
```

### KPIs (at every level)
- Days of Diesel Left, Total Tank, Daily Burn, Diesel Needed
- Critical/Warning/Safe site counts
- Total Sales, Diesel Cost, Diesel % of Sales
- With formula + source reference on every card

### 68 Charts
- Gen Hours vs Fuel, Efficiency, Buffer Days, Diesel Cost, Sales vs Diesel, Blackout
- By Sector breakdown, Rolling 3-day averages
- Site-level: 22+ trend charts with Daily/Weekly/Monthly period selector

### 15 Predictions & Forecasts
| # | Prediction | Model |
|---|-----------|-------|
| 1 | Fuel Consumption Forecast (7-day) | Linear Regression |
| 2 | Buffer Depletion Timeline | Per-site ranking |
| 3 | Weekly Budget Forecast | Price x Consumption |
| 4 | Blackout Duration Forecast | Linear Trend |
| 5 | Sales Impact (Blackout Correlation) | Dual-axis analysis |
| 6 | Generator Failure Risk | Threshold-based |
| 7 | Optimal Delivery Schedule | Buffer-based urgency |
| 8 | Diesel Price Alert | Ridge Regression forecast |
| 9 | Store Open/Close Recommendation | Diesel% thresholds |
| 10 | Fuel Theft Probability | Anomaly scoring |
| 11 | Efficiency Forecast | Linear Trend |
| 12 | Buffer Days Forecast | Linear Trend |
| 13 | Gen Hours Forecast | Linear Trend |
| 14 | Diesel Cost Forecast | Price x Consumption |
| 15 | Cross-Site Transfer Opportunities | Surplus/deficit matching |

### Operations
- Operating Modes (FULL/REDUCED/CLOSE per site)
- Delivery Queue (urgency + liters + cost)
- BCP Risk Scores (A-F grades)
- Stockout Forecast (7-day)
- Generator Fleet Status
- Maintenance Alerts
- Anomaly Detection (30%+ above average)
- Load Optimization ranking

### Peak Hours Heatmap
- Hour x Day-of-week grid showing profitability vs diesel cost
- Icons: 🟢 PEAK, 🟡 PROFITABLE, 🟠 MARGINAL, 🔴 LOSING
- Auto-recommendation: "Close after 8pm on weekdays"

### Regular vs LNG Comparison
- Side-by-side KPI cards + 6 comparison charts
- Filter by Site Type (All/Regular/LNG)

### Heatmap Tables (icons only, no colors)
- 🟢🟡🟠🔴 icons with values — works in Excel downloads too
- Diesel Price, Blackout Hr, Expense %, Buffer Days thresholds

### Dictionary Tab
- All KPI definitions, formulas, thresholds, icon meanings, data sources

## Quick Start

### Docker (recommended)
```bash
git clone https://github.com/raahulgupta07/CityBCPAgent.git
cd CityBCPAgent/CityBCPAgentv1
cp .env.example .env
# Edit .env with your OpenRouter API key
docker-compose up -d --build
# Open http://localhost:8501
# Login: admin / admin123
# Upload data via Data Entry page
```

### Local Development
```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Data Input

Database starts **empty**. Upload Excel files via Data Entry page. Auto-detects file type by sheet names.

| File | Sheets | Purpose |
|---|---|---|
| Blackout Hr_ CFC.xlsx | `CFC` | CFC generators + fuel + blackout |
| Blackout Hr_ CMHL.xlsx | `CMHL` | CMHL generators + fuel + blackout |
| Blackout Hr_ CP.xlsx | `CP` | CP generators + fuel + blackout |
| Blackout Hr_ PG.xlsx | `PG` | PG generators + fuel + blackout |
| Daily Fuel Price.xlsx | `CMHL, CP, CFC, PG` | Fuel purchase prices |
| CMHL_DAILY_SALES.xlsx | `daily sales, hourly sales, STORE MASTER` | Sales + store master |
| Diesel Expense LY.xlsx | — | Last year baseline |

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + streamlit-shadcn-ui + ECharts |
| Database | SQLite (WAL mode, 20+ tables) |
| ML | scikit-learn (Ridge, Isolation Forest, Gradient Boosting) |
| AI | Claude Haiku 4.5 via OpenRouter |
| Auth | Session tokens + URL params |
| Container | Docker on port 8501 |

## Environment Variables
```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
SUPER_ADMIN_USER=admin
SUPER_ADMIN_PASS=change-this-password
```

## License

Private project for City Holdings Myanmar.
