// KPI & Chart definitions for InfoTip tooltips
// Single source of truth for all dashboard explanations

export interface KpiDef {
  title: string;
  description: string;
  formula: string;
  example?: string;
}

export const KPI = {
  // ═══════════════════════════════════════
  // OVERVIEW TAB — Top KPI Cards
  // ═══════════════════════════════════════
  overview: {
    sites: {
      title: 'SITES',
      description: 'Total number of active sites (stores/properties) being monitored in the selected sector and date range.',
      formula: 'COUNT(DISTINCT site_id) from daily data',
      example: 'If 60 sites reported data → SITES = 60',
    } as KpiDef,
    generators: {
      title: 'GENERATORS',
      description: 'Total number of backup generators currently active across all sites.',
      formula: 'COUNT(generators WHERE is_active = 1)',
      example: 'If 45 sites have 2 generators each → GENERATORS ≈ 90',
    } as KpiDef,
    tankBalance: {
      title: 'TANK BALANCE (L)',
      description: 'Total diesel fuel remaining across all site tanks right now. Each generator row represents a separate drum/tank, so we SUM all of them.',
      formula: 'SUM(spare_tank_balance) across all generators, all sites',
      example: '60 sites × avg 500L each = 30,000L total tank',
    } as KpiDef,
    burnPerDay: {
      title: 'BURN / DAY (L)',
      description: 'Average liters of diesel consumed per day across all sites. Shows how fast fuel is being used.',
      formula: 'SUM(total_daily_used) ÷ COUNT(distinct dates)',
      example: '74,700L used over 60 sites in 1 day = 1,245 L/day',
    } as KpiDef,
    dieselCost: {
      title: 'DIESEL COST (MMK)',
      description: 'Total cost of diesel consumed. Uses the latest purchase price for each sector on each date — not an average.',
      formula: 'SUM(daily_used × date_specific_price_per_liter)',
      example: '1,245L × 2,800 MMK/L = 3,486,000 MMK',
    } as KpiDef,
    sales: {
      title: 'SALES (MMK)',
      description: 'Total daily sales revenue reported by stores. Used to compare against diesel cost to see if running generators is profitable.',
      formula: 'SUM(sales_amt) from POS/sales data',
      example: 'If 60 stores sell avg 5M each = 300M total sales',
    } as KpiDef,
    dieselPct: {
      title: 'DIESEL % OF SALES',
      description: 'What percentage of sales revenue goes to diesel cost. Below 1% is healthy. Above 3% means diesel is eating into profits — consider closing that site during blackouts.',
      formula: '(Diesel Cost ÷ Sales) × 100',
      example: 'Cost 3.5M ÷ Sales 300M = 1.17%',
    } as KpiDef,
    perSite: {
      title: 'PER SITE',
      description: 'The total value divided by the number of active sites. Shows the average per location.',
      formula: 'Total Value ÷ COUNT(distinct sites)',
      example: 'Total fuel 74,700L ÷ 60 sites = 1,245 L/site',
    } as KpiDef,
  },

  // ═══════════════════════════════════════
  // SITE MODAL — Deep Dive KPI Cards
  // ═══════════════════════════════════════
  siteModal: {
    buffer: {
      title: 'BUFFER (DAYS)',
      description: 'How many days of fuel remain before this site runs out, based on recent consumption rate. Below 3 days is critical — order fuel immediately.',
      formula: 'Current Tank Balance ÷ 3-day Average Daily Burn',
      example: 'Tank 1,500L ÷ avg burn 300L/day = 5.0 days buffer',
    } as KpiDef,
    tank: {
      title: 'TANK BALANCE (L)',
      description: 'Total liters of diesel remaining in all tanks/drums at this site right now.',
      formula: 'SUM(spare_tank_balance) across all generators at site',
      example: 'Gen1: 800L + Gen2: 700L = 1,500L total',
    } as KpiDef,
    fuelUsed: {
      title: 'FUEL USED (L)',
      description: 'Total liters of diesel consumed at this site on the selected day (or daily average for week/month).',
      formula: 'SUM(daily_used_liters) across all generators at site',
      example: 'Gen1: 180L + Gen2: 120L = 300L total',
    } as KpiDef,
    genHr: {
      title: 'GEN RUN HR',
      description: 'Total hours all generators ran at this site. Higher hours mean more blackout time.',
      formula: 'SUM(gen_run_hr) across all generators at site',
      example: 'Gen1: 8hr + Gen2: 6hr = 14hr total',
    } as KpiDef,
    blackout: {
      title: 'BLACKOUT HR',
      description: 'Hours without city power at this site. Generators run during blackouts to keep the store open.',
      formula: 'blackout_hr from daily site summary (reported value)',
      example: '10 hours blackout = generators ran for ~10 hours',
    } as KpiDef,
    cost: {
      title: 'DIESEL COST (MMK)',
      description: 'Total diesel cost at this site = fuel consumed × price per liter for that sector.',
      formula: 'SUM(daily_used) × sector_fuel_price_per_liter',
      example: '300L × 2,800 MMK/L = 840,000 MMK',
    } as KpiDef,
  },

  // ═══════════════════════════════════════
  // SITE MODAL — Charts
  // ═══════════════════════════════════════
  siteCharts: {
    bufferTrend: {
      title: 'Buffer Days Trend',
      description: 'Shows how many days of fuel remain over time. The green line (7 days) is safe, the red line (3 days) is critical. If the trend is going down, fuel is running out faster than it is being refilled.',
      formula: 'Buffer = Tank Balance ÷ 3-day avg burn. <b>Green line</b> = 7 days (safe), <b>Red line</b> = 3 days (critical)',
    } as KpiDef,
    efficiency: {
      title: 'Efficiency — L per Gen Hour',
      description: 'How many liters the generator burns per hour of operation. A sudden spike means the generator is consuming more fuel than normal — possible leak, theft, or mechanical issue.',
      formula: 'Fuel Used (L) ÷ Gen Run Hours',
      example: '300L ÷ 14hr = 21.4 L/hr',
    } as KpiDef,
    genVsFuel: {
      title: 'Gen Hours vs Fuel',
      description: 'Compares run time (bars) against fuel consumption (line). They should move together — if fuel goes up but hours stay flat, investigate.',
      formula: 'Bars = Gen Run Hr, Line = Fuel Used (L)',
    } as KpiDef,
    dailyVsTank: {
      title: 'Daily Used vs Tank Balance',
      description: 'Shows daily fuel consumption (bars) vs remaining tank (line). When bars are high and the line drops fast, this site needs a delivery.',
      formula: 'Bars = Daily Used (L), Line = Tank Balance (L)',
    } as KpiDef,
    cumulativeFuel: {
      title: 'Cumulative Fuel Consumption',
      description: 'Running total of all fuel used over time. A steeper slope means fuel is being consumed faster. Useful for budget tracking.',
      formula: 'Running SUM of daily fuel used from first day to each date',
    } as KpiDef,
    dailyCost: {
      title: 'Daily Diesel Cost',
      description: 'How much money this site spent on diesel each day.',
      formula: 'Daily Used (L) × Fuel Price per Liter (MMK)',
    } as KpiDef,
    blackoutVsFuel: {
      title: 'Blackout vs Fuel',
      description: 'Compares blackout hours (bars) with fuel consumed (line). More blackout = more fuel used. If fuel is high but blackout is low, generators may be running unnecessarily.',
      formula: 'Bars = Blackout Hr, Line = Fuel Used (L)',
    } as KpiDef,
    blackoutHours: {
      title: 'Daily Blackout Hours',
      description: 'Hours without city power each day. Helps predict when blackouts are worst and plan fuel deliveries.',
      formula: 'Reported blackout hours from Excel data',
    } as KpiDef,
    fuelPriceTrend: {
      title: 'Fuel Price Trend',
      description: 'Diesel purchase price over time for this sector. Shows if prices are rising or falling. In week/month view, shows the average price for that period.',
      formula: 'Daily: actual price/L | Weekly/Monthly: AVG(price/L) for the period',
    } as KpiDef,
    anomaly: {
      title: 'Anomaly Detection — Fuel vs 7-Day MA',
      description: 'Compares daily fuel use against its 7-day moving average. Days where actual fuel exceeds 130% of the average are flagged as anomalies — possible theft or waste.',
      formula: '7-Day MA = AVG(last 7 days fuel). <b>Anomaly</b> = actual &gt; 1.3 × 7-Day MA',
    } as KpiDef,
    siteVsSector: {
      title: 'Site vs Sector Average',
      description: 'Compares this site against the sector average. If this site uses much more fuel than the sector average, it may need attention.',
      formula: 'Blue = this site value, Orange = AVG of all sites in same sector',
    } as KpiDef,
    runHoursPerGen: {
      title: 'Run Hours per Generator',
      description: 'How many hours each generator ran. If one generator dominates, the rotation policy needs review — uneven load wears out equipment faster.',
      formula: 'SUM(gen_run_hr) per generator per day/week/month',
    } as KpiDef,
    fuelPerGen: {
      title: 'Fuel Used per Generator (L)',
      description: 'How many liters each generator consumed. Compare with run hours — a generator using lots of fuel for few hours is inefficient.',
      formula: 'SUM(daily_used_liters) per generator per day/week/month',
    } as KpiDef,
    expectedVsActual: {
      title: 'Expected vs Actual Consumption',
      description: 'Expected = what the generator SHOULD use based on its rated spec. Actual = what it REALLY used. Large gaps mean theft, leaks, or aging equipment.',
      formula: 'Expected = Rated L/Hr × Run Hours. Actual = Reported fuel used. Variance = Actual − Expected',
      example: 'Rated 15 L/hr × 10hr = 150L expected. Actual 200L = 50L variance (possible issue)',
    } as KpiDef,
    costSplit: {
      title: 'Cost Split by Generator',
      description: 'Which generator costs the most? If one slice dominates the pie, consider replacing or servicing that unit.',
      formula: 'Each slice = Liters Used × Price per Liter, grouped by generator',
    } as KpiDef,
    salesVsCost: {
      title: 'Sales vs Diesel Cost',
      description: 'Compares store revenue (bars) against diesel cost (line). If diesel cost is a large portion of sales, the store may not be profitable during blackouts.',
      formula: 'Bars = Daily Sales (MMK), Line = Diesel Cost (MMK)',
    } as KpiDef,
    dieselPctTrend: {
      title: 'Diesel % of Sales',
      description: 'What percentage of revenue goes to diesel. Green zone (below 0.9%) is healthy. Red zone (above 3%) means consider closing during blackouts.',
      formula: '(Diesel Cost ÷ Sales) × 100. <b>Green</b> &lt; 0.9%, <b>Red</b> &gt; 3%',
    } as KpiDef,
  },

  // ═══════════════════════════════════════
  // RISK TAB
  // ═══════════════════════════════════════
  risk: {
    sitesAtRisk: {
      title: 'SITES AT RISK',
      description: 'Number of sites with 7 or fewer days of fuel remaining. These sites need fuel delivery soon.',
      formula: 'COUNT(sites WHERE days_until_stockout &le; 7)',
      example: '15 out of 60 sites have less than 7 days fuel = 15 at risk',
    } as KpiDef,
    avgDaysToStockout: {
      title: 'AVG DAYS TO STOCKOUT',
      description: 'Average number of days before sites run out of fuel. Lower = more urgent. Below 5 days means many sites are critical.',
      formula: 'AVG(days_until_stockout) across all forecasted sites',
    } as KpiDef,
    mostUrgent: {
      title: 'MOST URGENT SITE',
      description: 'The site closest to running out of fuel. This site needs immediate attention — order fuel now.',
      formula: 'MIN(days_until_stockout) — the site with the fewest days left',
    } as KpiDef,
    bcpGrades: {
      title: 'BCP GRADE',
      description: 'Overall Business Continuity score for a site. A = excellent preparedness, F = critical risk. Based on 4 weighted factors.',
      formula: 'BCP Score = Fuel(35%) + Coverage(30%) + Power(20%) + Resilience(15%). Grade: A &ge; 80, B &ge; 60, C &ge; 40, D &ge; 20, F &lt; 20',
      example: 'Fuel=90 × 0.35 + Coverage=70 × 0.30 + Power=80 × 0.20 + Resilience=60 × 0.15 = 77.5 → Grade B',
    } as KpiDef,
    alertSeverity: {
      title: 'ALERT SEVERITY',
      description: 'Active alerts grouped by urgency. CRITICAL = act now, WARNING = monitor closely, INFO = awareness only.',
      formula: 'COUNT(alerts) grouped by severity level',
    } as KpiDef,
    breakEven: {
      title: 'BREAK-EVEN ANALYSIS',
      description: 'Shows whether a site earns enough to justify running generators. If diesel % is too high, the store loses money staying open during blackouts.',
      formula: 'Diesel % = (Avg Daily Fuel × Price) ÷ Avg Daily Sales × 100. If &gt; 3%, recommend CLOSE.',
    } as KpiDef,
  },

  // ═══════════════════════════════════════
  // OPERATIONS TAB
  // ═══════════════════════════════════════
  operations: {
    operatingModes: {
      title: 'OPERATING MODES',
      description: 'Recommended operating mode for each site based on diesel cost vs revenue. FULL = keep open, MONITOR = watch closely, REDUCE = cut hours, CLOSE = shut down during blackout.',
      formula: 'Based on diesel % of sales: FULL (&lt; 1%), MONITOR (1-2%), REDUCE (2-3%), CLOSE (&gt; 3%)',
    } as KpiDef,
    deliveryQueue: {
      title: 'DELIVERY QUEUE',
      description: 'Sites that need fuel delivery, sorted by urgency. CRITICAL = less than 3 days, HIGH = 3-5 days, MEDIUM = 5-7 days.',
      formula: 'Priority = based on days_until_stockout. Liters needed = (7 × avg_daily_burn) − current_tank',
      example: 'Site has 2 days left, burns 200L/day, tank=400L. Needs (7×200)−400 = 1,000L delivery',
    } as KpiDef,
    generatorRisk: {
      title: 'GENERATOR RISK',
      description: 'Generators flagged for potential issues — high efficiency ratio (fuel leak/theft), excessive hours, or maintenance overdue.',
      formula: 'Risk = HIGH if efficiency &gt; 1.5× rated | running &gt; 18hr/day | variance &gt; 30%',
    } as KpiDef,
  },

  // ═══════════════════════════════════════
  // FUEL INTEL TAB
  // ═══════════════════════════════════════
  fuelIntel: {
    buySignal: {
      title: 'SHOULD WE BUY FUEL?',
      description: 'Compares prices across suppliers and shows which is cheapest. Also checks if prices are trending up (buy now) or down (wait).',
      formula: 'Compare latest price/L across all suppliers. Show savings vs most expensive.',
    } as KpiDef,
    weeklyBudget: {
      title: 'WEEKLY BUDGET FORECAST',
      description: 'Estimated diesel cost for next week per sector, based on average daily consumption and current fuel prices.',
      formula: 'Weekly Cost = Avg Daily Liters × 7 × Current Price/L, per sector',
    } as KpiDef,
    priceForecast: {
      title: 'PRICE FORECAST',
      description: 'Predicted fuel price for the next 7 days using Ridge Regression on historical prices. R² shows prediction accuracy.',
      formula: 'Ridge Regression on last 30-60 days of prices. Features: trend + day-of-week seasonality.',
    } as KpiDef,
  },

  // ═══════════════════════════════════════
  // WASTE & THEFT
  // ═══════════════════════════════════════
  waste: {
    wasteRatio: {
      title: 'WASTE RATIO',
      description: 'How much more fuel a generator uses compared to its rated specification. A ratio of 1.0 is normal. Above 1.3 is suspicious — possible theft or leak.',
      formula: 'Waste Ratio = Actual L/Hr ÷ Rated L/Hr. Score = (Ratio − 1) × 100',
      example: 'Actual 18 L/hr ÷ Rated 15 L/hr = 1.20 ratio → 20% waste score',
    } as KpiDef,
    weekOverWeek: {
      title: 'WEEK OVER WEEK',
      description: 'Compares this week vs last week for key metrics. Green arrow = improved, Red arrow = worsened.',
      formula: 'Change % = (This Week − Last Week) ÷ Last Week × 100',
    } as KpiDef,
  },

  // ═══════════════════════════════════════
  // SECTOR SITES TABLE
  // ═══════════════════════════════════════
  sectorSites: {
    sales1d: {
      title: 'SALES 1D',
      description: 'Sales revenue for the most recent day of data.',
      formula: 'SUM(sales_amt) for last date in range',
    } as KpiDef,
    sales3d: {
      title: 'SALES 3D',
      description: 'Average daily sales over the last 3 days.',
      formula: 'AVG(daily sales) over last 3 dates',
    } as KpiDef,
    expPct1d: {
      title: 'EXP% 1D',
      description: 'Diesel expense as percentage of sales for the last day.',
      formula: '(Diesel Cost 1D ÷ Sales 1D) × 100',
    } as KpiDef,
    lyDieselPct: {
      title: 'LY D%',
      description: 'Last year diesel percentage — baseline from previous year for comparison.',
      formula: 'From uploaded LY diesel expense file: pct_on_sales',
    } as KpiDef,
  },
} as const;
