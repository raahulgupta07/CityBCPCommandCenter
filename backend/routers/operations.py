"""Operations router — modes, delivery, BCP scores, alerts, predictions."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends
import pandas as pd
from models.decision_engine import (
    get_operating_modes, get_delivery_queue,
    get_weekly_budget_forecast, get_supplier_buy_signal,
)
from models.bcp_engine import compute_bcp_scores
from models.buffer_predictor import get_critical_sites
from models.fuel_price_forecast import forecast_fuel_price
from alerts.alert_engine import get_active_alerts
from utils.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter()


def _enrich_site_code(df):
    """Add site_code (region) column from sites table if df has site_id."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df
    if "site_id" not in df.columns:
        return df
    try:
        with get_db() as conn:
            sites = pd.read_sql_query("SELECT site_id, region as site_code FROM sites", conn)
        df = df.merge(sites, on="site_id", how="left")
        df["site_code"] = df["site_code"].fillna("")
    except Exception:
        if "site_code" not in df.columns:
            df["site_code"] = ""
    return df


def _df_to_json(df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return df.fillna("").to_dict(orient="records")


@router.get("/operating-modes")
def operating_modes(sector: Optional[str] = None, site_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    df = get_operating_modes()
    if not df.empty and sector:
        df = df[df["sector_id"] == sector]
    if not df.empty and site_type and site_type != 'All' and "site_type" in df.columns:
        df = df[df["site_type"] == site_type]
    return _df_to_json(_enrich_site_code(df))


@router.get("/delivery-queue")
def delivery_queue(sector: Optional[str] = None, site_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    df = get_delivery_queue()
    if not df.empty and sector:
        df = df[df["sector_id"] == sector]
    if not df.empty and site_type and site_type != 'All' and "site_type" in df.columns:
        df = df[df["site_type"] == site_type]
    return _df_to_json(_enrich_site_code(df))


@router.get("/bcp-scores")
def bcp_scores(site_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        best_date = conn.execute("SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    if not best_date:
        return []
    df = compute_bcp_scores(best_date[0])
    if not df.empty and site_type and site_type != 'All':
        if "site_type" in df.columns:
            df = df[df["site_type"] == site_type]
        elif "site_id" in df.columns:
            with get_db() as conn:
                type_sites = pd.read_sql_query("SELECT site_id FROM sites WHERE site_type = ?", conn, params=[site_type])
            df = df[df["site_id"].isin(type_sites["site_id"])]
    return _df_to_json(_enrich_site_code(df))


@router.get("/alerts")
def alerts(site_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    df = get_active_alerts()
    if isinstance(df, pd.DataFrame) and not df.empty and site_type and site_type != 'All':
        if "site_type" in df.columns:
            df = df[df["site_type"] == site_type]
        elif "site_id" in df.columns:
            with get_db() as conn:
                type_sites = pd.read_sql_query("SELECT site_id FROM sites WHERE site_type = ?", conn, params=[site_type])
            df = df[df["site_id"].isin(type_sites["site_id"])]
    return _df_to_json(_enrich_site_code(df))


@router.get("/stockout-forecast")
def stockout_forecast(site_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    try:
        df = get_critical_sites(threshold_days=7)
        if not df.empty and site_type and site_type != 'All':
            if "site_type" in df.columns:
                df = df[df["site_type"] == site_type]
            elif "site_id" in df.columns:
                with get_db() as conn:
                    type_sites = pd.read_sql_query("SELECT site_id FROM sites WHERE site_type = ?", conn, params=[site_type])
                df = df[df["site_id"].isin(type_sites["site_id"])]
        return _df_to_json(_enrich_site_code(df))
    except Exception as e:
        logging.error(f"Error in stockout_forecast: {e}")
        return []


@router.get("/fuel-forecast")
def fuel_forecast(user: dict = Depends(get_current_user)):
    try:
        fc = forecast_fuel_price()
        if fc and not fc.get("error"):
            result = {
                "history": _df_to_json(fc.get("history")),
                "forecast": _df_to_json(fc.get("forecast")),
                "trend": fc.get("trend"),
                "r_squared": fc.get("r_squared"),
            }
            # Include GBR and ensemble forecasts if available
            if fc.get("gbr_forecast"):
                result["gbr_forecast"] = fc["gbr_forecast"]
                result["gbr_r2"] = fc.get("gbr_r2")
                result["gbr_trend"] = fc.get("gbr_trend")
            if fc.get("ensemble_forecast"):
                result["ensemble_forecast"] = fc["ensemble_forecast"]
            return result
    except Exception as e:
        logging.error(f"Error in fuel_forecast: {e}")
    return {"history": [], "forecast": [], "trend": "unknown", "r_squared": 0}


@router.get("/budget-forecast")
def budget_forecast(user: dict = Depends(get_current_user)):
    try:
        return get_weekly_budget_forecast() or {}
    except Exception as e:
        logging.error(f"Error in budget_forecast: {e}")
        return {}


@router.get("/buy-signal")
def buy_signal(user: dict = Depends(get_current_user)):
    try:
        return get_supplier_buy_signal() or {}
    except Exception as e:
        logging.error(f"Error in buy_signal: {e}")
        return {}
