"""
M2: Buffer Depletion Predictor
Two methods:
  1. Exponential smoothing (original) — simple, works with 2+ data points
  2. Ridge regression + day-of-week (new) — better accuracy, needs 5+ data points
     Projects 7-day cumulative burn, compares to tank balance.
     Confidence = R² score (0-100%).
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from utils.database import get_db


def ar_forecast(daily_values: list, horizon: int = 7) -> dict:
    """Simple autoregressive AR(3) forecast for fuel consumption using sklearn.
    Uses last 3 days as features to predict next day, then rolls forward.
    """
    if not daily_values or len(daily_values) < 7:
        return {"forecast": [], "method": "ar3", "r2": 0}

    vals = np.array(daily_values, dtype=float)

    # Build AR(3) features: X = [val(t-3), val(t-2), val(t-1)], y = val(t)
    lag = 3
    X = np.array([vals[i:i+lag] for i in range(len(vals) - lag)])
    y = vals[lag:]

    model = LinearRegression()
    model.fit(X, y)
    r2 = model.score(X, y)

    # Forecast: roll forward
    forecast = []
    window = list(vals[-lag:])
    for d in range(horizon):
        pred = float(model.predict(np.array([window[-lag:]]))[0])
        pred = max(0, pred)  # Can't be negative
        forecast.append(round(pred, 1))
        window.append(pred)

    return {
        "forecast": forecast,
        "method": "ar3",
        "r2": round(float(r2), 4),
    }


def predict_buffer_depletion(site_id=None, alpha=0.3, method="ridge"):
    """
    Predict when sites will run out of fuel based on consumption trends.

    Args:
        site_id: Optional specific site (None = all sites)
        alpha: Exponential smoothing factor (0-1, higher = more weight on recent data)
        method: "ridge" (default, better) or "ema" (original exponential smoothing)

    Returns:
        DataFrame with columns:
            site_id, sector_id, current_balance, avg_daily_used,
            smoothed_daily_used, days_until_stockout, projected_stockout_date,
            trend, confidence, confidence_pct, data_points, method
    """
    with get_db() as conn:
        query = """
            SELECT dss.site_id, s.sector_id, dss.date,
                   dss.total_daily_used, dss.spare_tank_balance, dss.days_of_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.total_daily_used > 0 OR dss.spare_tank_balance > 0
        """
        params = []
        if site_id:
            query += " AND dss.site_id = ?"
            params.append(site_id)
        query += " ORDER BY dss.site_id, dss.date"
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return pd.DataFrame()

    results = []
    for sid, group in df.groupby("site_id"):
        group = group.sort_values("date")
        sector = group["sector_id"].iloc[0]

        usage = group["total_daily_used"].dropna()
        if len(usage) < 2:
            continue

        balance_series = group["spare_tank_balance"].dropna()
        if balance_series.empty:
            continue
        current_balance = balance_series.iloc[-1]

        avg_daily = usage.mean()

        # --- Exponential Smoothing (always computed for fallback) ---
        smoothed = usage.iloc[0]
        for val in usage.iloc[1:]:
            smoothed = alpha * val + (1 - alpha) * smoothed

        # --- Trend detection ---
        if len(usage) >= 6:
            recent = usage.iloc[-3:].mean()
            earlier = usage.iloc[-6:-3].mean()
            pct_change = (recent - earlier) / earlier * 100 if earlier > 0 else 0
            trend = "increasing" if pct_change > 10 else "decreasing" if pct_change < -10 else "stable"
        elif len(usage) >= 3:
            recent = usage.iloc[-2:].mean()
            earlier = usage.iloc[:-2].mean()
            pct_change = (recent - earlier) / earlier * 100 if earlier > 0 else 0
            trend = "increasing" if pct_change > 10 else "decreasing" if pct_change < -10 else "stable"
        else:
            trend = "stable"

        # --- Method selection ---
        used_method = "ema"
        r_squared = None
        predicted_7d_burn = None

        if method == "ridge" and len(usage) >= 5:
            result = _ridge_forecast(group, usage, current_balance)
            if result:
                used_method = "ridge"
                days_until = result["days_until"]
                r_squared = result["r_squared"]
                predicted_7d_burn = result["predicted_7d_burn"]
                confidence_pct = round(max(0, min(100, r_squared * 100)))
                if confidence_pct >= 70:
                    confidence = "high"
                elif confidence_pct >= 40:
                    confidence = "medium"
                else:
                    confidence = "low"
            else:
                # Fallback to EMA
                days_until, confidence, confidence_pct = _ema_stockout(
                    current_balance, smoothed, avg_daily, usage
                )
        else:
            days_until, confidence, confidence_pct = _ema_stockout(
                current_balance, smoothed, avg_daily, usage
            )

        # Projected date
        latest_date = pd.to_datetime(group["date"].max())
        stockout_date = None
        if days_until is not None and days_until < 365:
            stockout_date = (latest_date + timedelta(days=int(days_until))).strftime("%Y-%m-%d")

        # --- AR(3) forecast alongside existing method ---
        daily_fuel_values = usage.tolist()
        ar = ar_forecast(daily_fuel_values)

        # --- Monte Carlo stockout simulation (last 30 days of burns) ---
        mc_burns = usage.iloc[-30:].tolist()  # Last 14-30 days of consumption
        mc = monte_carlo_stockout(current_balance, mc_burns)

        result = {
            "site_id": sid,
            "sector_id": sector,
            "current_balance": round(current_balance, 0),
            "avg_daily_used": round(avg_daily, 1),
            "smoothed_daily_used": round(smoothed, 1),
            "days_until_stockout": round(days_until, 1) if days_until else None,
            "projected_stockout_date": stockout_date,
            "trend": trend,
            "confidence": confidence,
            "confidence_pct": confidence_pct,
            "data_points": len(usage),
            "method": used_method,
            "predicted_7d_burn": round(predicted_7d_burn, 0) if predicted_7d_burn else None,
            "ar_forecast": ar["forecast"],
            "ar_r2": ar["r2"],
            "ar_method": ar["method"],
            "mc_p10": mc["p10_days"],
            "mc_p50": mc["p50_days"],
            "mc_p90": mc["p90_days"],
            "mc_mean": mc["mean_days"],
            "mc_mean_burn": mc.get("mean_burn"),
            "mc_std_burn": mc.get("std_burn"),
            "confidence_band": mc["confidence_band"],
        }
        results.append(result)

    return pd.DataFrame(results)


def _ema_stockout(current_balance, smoothed, avg_daily, usage):
    """Original exponential smoothing stockout calculation."""
    consumption_rate = smoothed if smoothed > 0 else avg_daily
    if consumption_rate > 0:
        days_until = current_balance / consumption_rate
    else:
        days_until = None

    data_points = len(usage)
    usage_variance = usage.std() / usage.mean() if usage.mean() > 0 else 1
    if data_points >= 5 and usage_variance < 0.3:
        confidence = "high"
        confidence_pct = 80
    elif data_points >= 3:
        confidence = "medium"
        confidence_pct = 50
    else:
        confidence = "low"
        confidence_pct = 20

    return days_until, confidence, confidence_pct


def _ridge_forecast(group, usage, current_balance, forecast_days=7):
    """
    Ridge regression forecast with day-of-week feature.
    Predicts daily burn for next 7 days, sums cumulative burn,
    finds when cumulative burn exceeds tank balance.

    Returns dict with days_until, r_squared, predicted_7d_burn or None on failure.
    """
    try:
        from sklearn.linear_model import Ridge

        # Build features from historical data (last 30 days max)
        recent = group.tail(30).copy()
        recent["date_dt"] = pd.to_datetime(recent["date"])
        recent["day_of_week"] = recent["date_dt"].dt.dayofweek  # 0=Mon, 6=Sun
        recent["trend_idx"] = np.arange(len(recent))  # 0, 1, 2, ...

        y = recent["total_daily_used"].values
        X = np.column_stack([
            recent["trend_idx"].values,
            np.sin(2 * np.pi * recent["day_of_week"].values / 7),  # weekly cycle sin
            np.cos(2 * np.pi * recent["day_of_week"].values / 7),  # weekly cycle cos
        ])

        # Fit Ridge regression
        model = Ridge(alpha=1.0)
        model.fit(X, y)
        r_squared = model.score(X, y)

        # Predict next 7 days
        last_date = recent["date_dt"].iloc[-1]
        last_idx = recent["trend_idx"].iloc[-1]
        future_burns = []

        for d in range(1, forecast_days + 1):
            future_date = last_date + timedelta(days=d)
            dow = future_date.dayofweek
            idx = last_idx + d
            X_pred = np.array([[idx, np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7)]])
            pred = max(0, model.predict(X_pred)[0])  # burn can't be negative
            future_burns.append(pred)

        predicted_7d_burn = sum(future_burns)

        # Find days until stockout: accumulate daily burn until > tank
        cumulative = 0
        days_until = None
        for d, burn in enumerate(future_burns, 1):
            cumulative += burn
            if cumulative >= current_balance:
                # Interpolate: fraction of day when it crosses
                prev_cum = cumulative - burn
                remaining = current_balance - prev_cum
                fraction = remaining / burn if burn > 0 else 0
                days_until = d - 1 + fraction
                break

        if days_until is None:
            # Didn't run out in 7 days — extrapolate with avg predicted burn
            avg_future_burn = predicted_7d_burn / forecast_days if forecast_days > 0 else 0
            if avg_future_burn > 0:
                days_until = current_balance / avg_future_burn
            else:
                days_until = None

        return {
            "days_until": days_until,
            "r_squared": r_squared,
            "predicted_7d_burn": predicted_7d_burn,
        }
    except Exception:
        return None


def monte_carlo_stockout(tank_balance: float, daily_burns: list, n_simulations: int = 1000) -> dict:
    """Monte Carlo simulation for stockout prediction with confidence intervals."""
    if not daily_burns or len(daily_burns) < 3 or tank_balance <= 0:
        return {"p10_days": 0, "p50_days": 0, "p90_days": 0, "mean_days": 0,
                "confidence_band": [], "method": "monte_carlo", "simulations": n_simulations}

    burns = np.array(daily_burns, dtype=float)
    mean_burn = np.mean(burns)
    std_burn = max(np.std(burns), mean_burn * 0.05)  # At least 5% variation

    stockout_days = []
    for _ in range(n_simulations):
        remaining = tank_balance
        day = 0
        while remaining > 0 and day < 90:  # Cap at 90 days
            daily = max(0, np.random.normal(mean_burn, std_burn))
            remaining -= daily
            day += 1
        stockout_days.append(day)

    stockout_days = np.array(stockout_days)
    p10 = int(np.percentile(stockout_days, 10))
    p50 = int(np.percentile(stockout_days, 50))
    p90 = int(np.percentile(stockout_days, 90))

    # Build 7-day confidence band (remaining tank at each day)
    band = []
    for d in range(1, 8):
        cum_burns = np.array([
            sum(max(0, np.random.normal(mean_burn, std_burn)) for _ in range(d))
            for _ in range(n_simulations)
        ])
        remaining = tank_balance - cum_burns
        band.append({
            "day": d,
            "p10": round(max(0, float(np.percentile(remaining, 90))), 1),  # P90 remaining = P10 burn (optimistic)
            "p50": round(max(0, float(np.percentile(remaining, 50))), 1),
            "p90": round(max(0, float(np.percentile(remaining, 10))), 1),  # P10 remaining = P90 burn (pessimistic)
        })

    return {
        "p10_days": p10,
        "p50_days": p50,
        "p90_days": p90,
        "mean_days": round(float(np.mean(stockout_days)), 1),
        "confidence_band": band,
        "method": "monte_carlo",
        "simulations": n_simulations,
        "mean_burn": round(mean_burn, 1),
        "std_burn": round(std_burn, 1),
    }


def get_critical_sites(threshold_days=7):
    """Get sites projected to run out within threshold_days."""
    df = predict_buffer_depletion()
    if df.empty:
        return df
    critical = df[
        (df["days_until_stockout"].notna()) &
        (df["days_until_stockout"] <= threshold_days)
    ].sort_values("days_until_stockout")
    return critical
