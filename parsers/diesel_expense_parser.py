"""
Parser for Daily Avg Diesel Expense LY.xlsx
— Last 12-month average daily diesel expense per store.

Simple flat file with 3 sheets (CMHL, CP, CFC), no merged cells.
Join key: Cost Center Code (matches blackout file col D).
"""
import pandas as pd


def parse_diesel_expense_file(filepath):
    """
    Parse Daily Avg Diesel Expense LY file.

    Returns:
        {
            "records": [
                {
                    "cost_center_code": str,
                    "sector_id": str,
                    "cost_center_name": str,
                    "yearly_expense_mmk_mil": float,
                    "daily_avg_expense_mmk": float,
                    "pct_on_sales": float,
                }
            ],
            "sector_counts": {"CMHL": N, "CP": N, "CFC": N},
            "errors": [str],
        }
    """
    result = {"records": [], "sector_counts": {}, "errors": []}

    try:
        xl = pd.ExcelFile(str(filepath))
    except Exception as e:
        result["errors"].append(f"Cannot open file: {e}")
        return result

    for sheet_name in xl.sheet_names:
        sector_id = sheet_name.strip().upper()
        if sector_id not in ("CMHL", "CP", "CFC"):
            continue

        try:
            df = pd.read_excel(xl, sheet_name=sheet_name)
        except Exception as e:
            result["errors"].append(f"Cannot read sheet {sheet_name}: {e}")
            continue

        # Find columns by keyword matching (resilient to minor header changes)
        col_map = {}
        for col in df.columns:
            cl = str(col).lower().strip()
            if "cost center code" in cl or "cost_center_code" in cl:
                col_map["code"] = col
            elif "cost center" in cl and "code" not in cl:
                col_map["name"] = col
            elif "daily" in cl and ("avg" in cl or "average" in cl) and "diesel" in cl:
                col_map["daily_avg"] = col
            elif "yearly" in cl and "diesel" in cl:
                col_map["yearly"] = col
            elif "onsales" in cl or "on_sales" in cl or "%onsales" in cl:
                col_map["pct_sales"] = col
            elif "sector" in cl:
                col_map["sector"] = col

        if "code" not in col_map:
            result["errors"].append(f"Sheet {sheet_name}: no 'Cost Center Code' column found")
            continue

        count = 0
        for _, row in df.iterrows():
            code = row.get(col_map["code"])
            if pd.isna(code):
                continue

            code_str = str(int(code)) if isinstance(code, float) else str(code).strip()
            name = str(row.get(col_map.get("name"), "")).strip() if col_map.get("name") else ""
            daily_avg = _safe_float(row.get(col_map.get("daily_avg")))
            yearly = _safe_float(row.get(col_map.get("yearly")))
            pct = _safe_float(row.get(col_map.get("pct_sales")))

            if daily_avg is None and yearly is None:
                continue  # skip empty rows

            result["records"].append({
                "cost_center_code": code_str,
                "sector_id": sector_id,
                "cost_center_name": name,
                "yearly_expense_mmk_mil": yearly,
                "daily_avg_expense_mmk": daily_avg,
                "pct_on_sales": pct,
            })
            count += 1

        result["sector_counts"][sector_id] = count

    return result


def _safe_float(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
