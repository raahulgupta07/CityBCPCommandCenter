"""
Parser for storemaster.xlsx — 439 stores with segment, location, size.
Maps each store to a BCP sector using SEGMENT_SECTOR_MAP.
"""
import pandas as pd
from config.settings import SEGMENT_SECTOR_MAP


def parse_storemaster_file(filepath):
    """
    Parse storemaster Excel file.

    Returns:
        {
            "stores": [ { gold_code, pos_code, store_name, segment_id,
                          segment_name, company_code, legal_entity, channel,
                          address_state, address_township, latitude, longitude,
                          store_size, open_date, closed_date, sector_id } ],
            "errors": [str],
            "sector_counts": { sector_id: count },
        }
    """
    df = pd.read_excel(filepath, sheet_name=0)

    result = {"stores": [], "errors": [], "sector_counts": {}}

    # Identify columns (flexible matching)
    col_map = {}
    for col in df.columns:
        cl = str(col).strip().lower().replace(" ", "").replace("_", "")
        if "goldcode" in cl:
            col_map["gold_code"] = col
        elif "poscode" in cl:
            col_map["pos_code"] = col
        elif "costcenterdescription" in cl:
            col_map["cost_center_description"] = col
        elif "costcentername" in cl:
            col_map["cost_center_name"] = col
        elif "costcenter" in cl and "cost_center_code" not in col_map:
            col_map["cost_center_code"] = col
        elif "segmentname" in cl:
            col_map["segment_name"] = col
        elif "segment" in cl and "segment_id" not in col_map:
            col_map["segment_id"] = col
        elif "companycode" in cl:
            col_map["company_code"] = col
        elif "legalentity" in cl:
            col_map["legal_entity"] = col
        elif cl == "sector":
            col_map["sector"] = col
        elif "channel" in cl:
            col_map["channel"] = col
        elif "addressstate" in cl or "addressstate" in cl:
            col_map["address_state"] = col
        elif "addresstownship" in cl or "addresstownship" in cl:
            col_map["address_township"] = col
        elif "latitude" in cl:
            col_map["latitude"] = col
        elif "longitude" in cl:
            col_map["longitude"] = col
        elif "storesize" in cl:
            col_map["store_size"] = col
        elif "opendate" in cl:
            col_map["open_date"] = col
        elif "closeddate" in cl or "closedate" in cl:
            col_map["closed_date"] = col
        elif "cpcenterid" in cl or "cp_centerid" in cl:
            col_map["cp_center_id"] = col

    def _get(row, key, default=None):
        col = col_map.get(key)
        if col is None:
            return default
        val = row.get(col)
        if pd.isna(val):
            return default
        return val

    def _parse_coord(val):
        """Parse latitude/longitude — handles decimal, DMS (16°51'56.4"), or None."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if s in ("", "NULL", "null", "None"):
            return None
        # Try direct float
        try:
            return float(s)
        except ValueError:
            pass
        # Try DMS: 16°51'56.4"
        import re
        m = re.match(r"(\d+)[°](\d+)['\u2019](\d+\.?\d*)[\"″\u201d]?\s*([NSEW])?", s)
        if m:
            d, mi, sec = float(m.group(1)), float(m.group(2)), float(m.group(3))
            result = d + mi / 60 + sec / 3600
            if m.group(4) in ("S", "W"):
                result = -result
            return round(result, 8)
        return None

    def _clean_size(val):
        if val is None:
            return None
        s = str(val).strip().replace("(", "").replace(")", "").strip()
        if s.upper() in ("S", "M", "L", "XL"):
            return s.upper()
        return s

    def _format_date(val):
        if val is None or pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            s = str(int(val))
            if len(s) == 8:
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        return str(val)

    # Sector name → sector_id mapping (from the Sector column in Excel)
    _sector_name_map = {
        "retail": "CMHL", "property": "CP", "f&b": "CFC", "distribution": "PG",
    }

    for _, row in df.iterrows():
        gold_code = _get(row, "gold_code")
        if gold_code is None or pd.isna(gold_code):
            continue

        gold_code = str(gold_code).strip()
        segment_name = _get(row, "segment_name", "")
        segment_name = str(segment_name).strip() if segment_name else ""

        # Derive sector_id: first try Sector column, then segment mapping
        sector_raw = _get(row, "sector", "")
        sector_raw = str(sector_raw).strip() if sector_raw else ""
        sector_id = _sector_name_map.get(sector_raw.lower()) if sector_raw else None

        if not sector_id:
            sector_id = SEGMENT_SECTOR_MAP.get(segment_name)
        if not sector_id:
            # Try partial match
            for seg_key, sec_id in SEGMENT_SECTOR_MAP.items():
                if seg_key.lower() in segment_name.lower():
                    sector_id = sec_id
                    break

        # Use CostCenterName as store_name, fall back to gold_code
        cost_center_name = _get(row, "cost_center_name", "")
        cost_center_name = str(cost_center_name).strip() if cost_center_name else ""

        # Format cost_center_code (may be numeric in Excel)
        cc_raw = _get(row, "cost_center_code")
        cost_center_code = None
        if cc_raw is not None:
            cost_center_code = str(int(cc_raw)) if isinstance(cc_raw, float) else str(cc_raw).strip()

        store = {
            "gold_code": gold_code,
            "pos_code": str(_get(row, "pos_code", "")).strip(),
            "store_name": cost_center_name or gold_code,
            "cost_center_code": cost_center_code,
            "cost_center_name": cost_center_name,
            "cost_center_description": _get(row, "cost_center_description"),
            "segment_id": _get(row, "segment_id"),
            "segment_name": segment_name,
            "company_code": _get(row, "company_code"),
            "legal_entity": _get(row, "legal_entity"),
            "channel": _get(row, "channel"),
            "address_state": _get(row, "address_state"),
            "address_township": _get(row, "address_township"),
            "latitude": _parse_coord(_get(row, "latitude")),
            "longitude": _parse_coord(_get(row, "longitude")),
            "store_size": _clean_size(_get(row, "store_size")),
            "open_date": _format_date(_get(row, "open_date")),
            "closed_date": _format_date(_get(row, "closed_date")),
            "sector_id": sector_id,
            "cp_center_id": _get(row, "cp_center_id"),
        }
        result["stores"].append(store)

        if sector_id:
            result["sector_counts"][sector_id] = result["sector_counts"].get(sector_id, 0) + 1

    return result
