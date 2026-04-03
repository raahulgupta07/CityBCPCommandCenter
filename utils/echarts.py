"""
Reusable ECharts components for CityBCPAgent.
All charts use formatted tooltips. Labels shown only for small datasets.
Uses streamlit-echarts for rendering.
"""
from streamlit_echarts import st_echarts
from config.settings import SECTORS

# ─── Colors ──────────────────────────────────────────────────────────────────
SECTOR_COLORS = {sid: info["color"] for sid, info in SECTORS.items()}
STATUS_COLORS = {
    "CRITICAL": "#dc2626", "WARNING": "#d97706", "HEALTHY": "#16a34a",
    "OPEN": "#16a34a", "MONITOR": "#d97706", "REDUCE": "#ea580c",
    "CLOSE": "#dc2626", "NO SALES DATA": "#94a3b8", "NO DATA": "#94a3b8",
}
PALETTE = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
           "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1"]

DEFAULT_TOOLTIP = {
    "trigger": "axis",
    "axisPointer": {"type": "shadow"},
    "textStyle": {"fontSize": 12},
    "confine": True,
}

DEFAULT_GRID = {"left": "8%", "right": "8%", "bottom": "12%", "top": "15%", "containLabel": True}


def _clean(data):
    """Sanitise a list for ECharts: replace None/NaN with 0."""
    if not data:
        return []
    cleaned = []
    for v in data:
        if v is None:
            cleaned.append(0)
        elif isinstance(v, float) and (v != v):  # NaN check
            cleaned.append(0)
        else:
            cleaned.append(v)
    return cleaned


def _fmt_val(v):
    """Format a number for display: 1234567→'1.2M', 12345→'12.3K'."""
    if v is None or v == 0:
        return "0"
    a = abs(v)
    if a >= 1e9:
        return f"{v/1e9:.1f}B"
    if a >= 1e6:
        return f"{v/1e6:.1f}M"
    if a >= 1e4:
        return f"{v/1e3:.1f}K"
    if a >= 1e3:
        return f"{v:,.0f}"
    if a < 1 and a > 0:
        return f"{v:.2f}"
    return f"{v:,.1f}"


def _make_rich_data(values):
    """Convert values to [{value: num, name: 'formatted'}] for rich tooltip display."""
    cleaned = _clean(values)
    return [{"value": v, "name": _fmt_val(v)} for v in cleaned]


def _fmt(val, unit=""):
    """Format number for display."""
    if val is None:
        return "—"
    if abs(val) >= 1_000_000_000:
        return f"{val/1e9:,.1f}B{unit}"
    if abs(val) >= 1_000_000:
        return f"{val/1e6:,.1f}M{unit}"
    if abs(val) >= 1_000:
        return f"{val/1e3:,.1f}K{unit}"
    return f"{val:,.0f}{unit}"


# Tooltip format string — ECharts built-in: {a}=series, {b}=category, {c}=value
# For axis trigger, use a list format
_TOOLTIP_FMT = "{b}<br/>{a}: <b>{c}</b>"


# ═══════════════════════════════════════════════════════════════════════════
# CHART BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

def bar_chart(categories, values, title="", color="#3b82f6", unit="",
              height=400, horizontal=False, key=None):
    """Simple bar chart with numbers on each bar."""
    categories = _clean(categories); values = _clean(values)
    if not categories or not values: return
    # Show labels only for small datasets
    show_lbl = len(values) <= 15
    if horizontal:
        option = {
            "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {**DEFAULT_TOOLTIP, "trigger": "axis"},
            "grid": DEFAULT_GRID,
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": categories, "axisLabel": {"fontSize": 11}},
            "series": [{
                "type": "bar",
                "data": _make_rich_data(values),
                "label": {"show": show_lbl, "position": "right",
                          "fontSize": 11, "color": "#374151", "formatter": "{@name}"},
                "itemStyle": {"color": color},
            }],
        }
    else:
        option = {
            "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {**DEFAULT_TOOLTIP},
            "grid": DEFAULT_GRID,
            "xAxis": {"type": "category", "data": categories,
                      "axisLabel": {"rotate": 30 if len(categories) > 6 else 0, "fontSize": 11}},
            "yAxis": {"type": "value"},
            "series": [{
                "type": "bar",
                "data": _make_rich_data(values),
                "label": {"show": show_lbl, "position": "top", "fontSize": 11,
                          "color": "#374151", "formatter": "{@name}"},
                "itemStyle": {"color": color},
            }],
        }
    st_echarts(option, height=f"{height}px", key=key)


def grouped_bar(categories, series_list, title="", height=400, key=None):
    """
    Grouped bar chart. series_list = [{"name": str, "data": list, "color": str}, ...]
    """
    categories = _clean(categories)
    if not categories: return
    show_lbl = len(categories) <= 8
    series = []
    for s in series_list:
        series.append({
            "name": s["name"],
            "type": "bar",
            "data": _make_rich_data(s["data"]),
            "label": {"show": show_lbl, "position": "top", "fontSize": 10,
                      "color": "#374151", "formatter": "{@name}"},
            "itemStyle": {"color": s.get("color", PALETTE[len(series) % len(PALETTE)])},
        })
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {**DEFAULT_TOOLTIP},
        "legend": {"bottom": 0, "textStyle": {"fontSize": 11}},
        "grid": {**DEFAULT_GRID, "bottom": "18%"},
        "xAxis": {"type": "category", "data": categories,
                  "axisLabel": {"rotate": 30 if len(categories) > 6 else 0, "fontSize": 11}},
        "yAxis": {"type": "value"},
        "series": series,
    }
    st_echarts(option, height=f"{height}px", key=key)


def stacked_bar(categories, series_list, title="", height=400, key=None):
    """
    Stacked bar chart. series_list = [{"name": str, "data": list, "color": str}, ...]
    """
    categories = _clean(categories)
    if not categories: return
    series = []
    for s in series_list:
        series.append({
            "name": s["name"],
            "type": "bar",
            "stack": "total",
            "data": _make_rich_data(s["data"]),
            "label": {"show": True, "position": "inside", "fontSize": 10,
                      "color": "#fff", "formatter": "{@name}"},
            "itemStyle": {"color": s.get("color", PALETTE[len(series) % len(PALETTE)])},
            "emphasis": {"focus": "series"},
        })
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {**DEFAULT_TOOLTIP},
        "legend": {"bottom": 0, "textStyle": {"fontSize": 11}},
        "grid": {**DEFAULT_GRID, "bottom": "18%"},
        "xAxis": {"type": "category", "data": categories,
                  "axisLabel": {"rotate": 30 if len(categories) > 6 else 0, "fontSize": 11}},
        "yAxis": {"type": "value"},
        "series": series,
    }
    st_echarts(option, height=f"{height}px", key=key)


def line_chart(categories, series_list, title="", height=400,
               mark_lines=None, key=None):
    """
    Line chart. series_list = [{"name": str, "data": list, "color": str}, ...]
    mark_lines = [{"value": float, "label": str, "color": str}, ...]
    """
    categories = _clean(categories)
    if not categories: return
    n_series = len(series_list)
    show_lbl = len(categories) <= 10 and n_series <= 2
    series = []
    for s in series_list:
        sdata = _clean(s["data"])
        entry = {
            "name": s["name"],
            "type": "line",
            "data": _make_rich_data(sdata),
            "label": {"show": show_lbl, "position": "top",
                      "fontSize": 10, "color": "#374151", "formatter": "{@name}"},
            "symbol": "circle",
            "symbolSize": 6,
            "lineStyle": {"width": 2},
            "itemStyle": {"color": s.get("color", PALETTE[len(series) % len(PALETTE)])},
        }
        if mark_lines and len(series) == 0:
            entry["markLine"] = {
                "data": [
                    {"yAxis": ml["value"], "name": ml["label"],
                     "lineStyle": {"color": ml.get("color", "#ef4444"), "type": "dashed"},
                     "label": {"formatter": ml["label"], "fontSize": 10}}
                    for ml in mark_lines
                ],
                "silent": True,
            }
        series.append(entry)
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {**DEFAULT_TOOLTIP},
        "legend": {"bottom": 0, "textStyle": {"fontSize": 11}},
        "grid": {**DEFAULT_GRID, "bottom": "18%"},
        "xAxis": {"type": "category", "data": categories, "axisLabel": {"fontSize": 11}},
        "yAxis": {"type": "value"},
        "series": series,
    }
    st_echarts(option, height=f"{height}px", key=key)


def dual_axis_chart(categories, bar_series, line_series, title="",
                    bar_name="", line_name="", bar_color="#3b82f6",
                    line_color="#ef4444", height=400, key=None):
    """Bar + Line on dual Y axes, both with numbers."""
    categories = _clean(categories); bar_series = _clean(bar_series); line_series = _clean(line_series)
    if not categories: return
    show_lbl = len(categories) <= 12
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {**DEFAULT_TOOLTIP},
        "legend": {"bottom": 0, "data": [bar_name, line_name], "textStyle": {"fontSize": 11}},
        "grid": {**DEFAULT_GRID, "bottom": "18%"},
        "xAxis": {"type": "category", "data": categories, "axisLabel": {"fontSize": 11}},
        "yAxis": [
            {"type": "value", "name": bar_name, "nameTextStyle": {"fontSize": 11}},
            {"type": "value", "name": line_name, "nameTextStyle": {"fontSize": 11}},
        ],
        "series": [
            {
                "name": bar_name, "type": "bar", "data": _make_rich_data(bar_series),
                "label": {"show": show_lbl, "position": "top", "fontSize": 10,
                          "color": "#374151", "formatter": "{@name}"},
                "itemStyle": {"color": bar_color},
            },
            {
                "name": line_name, "type": "line", "yAxisIndex": 1,
                "data": _make_rich_data(line_series),
                "label": {"show": False},
                "symbol": "circle", "symbolSize": 6,
                "lineStyle": {"width": 2, "color": line_color},
                "itemStyle": {"color": line_color},
            },
        ],
    }
    st_echarts(option, height=f"{height}px", key=key)


def pie_chart(data, title="", height=350, key=None):
    """
    Pie chart with name + value + percentage.
    data = [{"name": str, "value": float}, ...] or [{"name": str, "value": float, "color": str}, ...]
    """
    if not data: return
    colors = [d.get("color", PALETTE[i % len(PALETTE)]) for i, d in enumerate(data)]
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c:,.0f} ({d}%)"},
        "color": colors,
        "series": [{
            "type": "pie",
            "radius": ["35%", "70%"],
            "data": [{"name": d["name"], "value": d["value"]} for d in data],
            "label": {
                "show": True,
                "formatter": "{b}\n{c:,.0f}\n({d}%)",
                "fontSize": 11,
            },
            "emphasis": {
                "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}
            },
        }],
    }
    st_echarts(option, height=f"{height}px", key=key)


def scatter_chart(data, title="", x_name="", y_name="", height=400, key=None):
    """
    Scatter plot. data = [{"name": str, "x": float, "y": float, "size": float, "color": str}, ...]
    """
    # Group by color
    groups = {}
    for d in data:
        c = d.get("color", PALETTE[0])
        if c not in groups:
            groups[c] = {"name": d.get("group", ""), "data": []}
        groups[c]["data"].append([d["x"], d["y"], d.get("size", 10), d["name"]])

    series = []
    for color, group in groups.items():
        series.append({
            "name": group["name"],
            "type": "scatter",
            "data": [[d[0], d[1]] for d in group["data"]],
            "symbolSize": 12,
            "itemStyle": {"color": color},
        })
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "grid": DEFAULT_GRID,
        "xAxis": {"type": "value", "name": x_name, "nameTextStyle": {"fontSize": 11}},
        "yAxis": {"type": "value", "name": y_name, "nameTextStyle": {"fontSize": 11}},
        "series": series,
    }
    st_echarts(option, height=f"{height}px", key=key)


def horizontal_bar(categories, values, title="", colors=None, height=None, key=None):
    """Horizontal bar chart with values on right."""
    categories = _clean(categories); values = _clean(values)
    if not categories or not values: return
    if height is None:
        height = max(350, len(categories) * 28)
    item_colors = colors if colors else [PALETTE[0]] * len(values)
    rich_data = []
    for v, c in zip(values, item_colors):
        rich_data.append({"value": v, "name": _fmt_val(v), "itemStyle": {"color": c}})
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {**DEFAULT_TOOLTIP, "trigger": "axis"},
        "grid": {"left": "25%", "right": "12%", "bottom": "8%", "top": "12%"},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "category", "data": categories, "axisLabel": {"fontSize": 11}},
        "series": [{
            "type": "bar",
            "data": rich_data,
            "label": {"show": True, "position": "right", "fontSize": 11,
                      "color": "#374151", "formatter": "{@name}"},
        }],
    }
    st_echarts(option, height=f"{height}px", key=key)
