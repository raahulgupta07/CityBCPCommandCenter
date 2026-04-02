"""
Reusable ECharts components for CityBCPAgent.
All charts show data labels (numbers) by default.
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
}

DEFAULT_GRID = {"left": "8%", "right": "8%", "bottom": "12%", "top": "15%", "containLabel": True}


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


# ═══════════════════════════════════════════════════════════════════════════
# CHART BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

def bar_chart(categories, values, title="", color="#3b82f6", unit="",
              height=400, horizontal=False, key=None):
    """Simple bar chart with numbers on each bar."""
    axis_type = "category"
    if horizontal:
        option = {
            "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {**DEFAULT_TOOLTIP, "trigger": "axis"},
            "grid": DEFAULT_GRID,
            "xAxis": {"type": "value"},
            "yAxis": {"type": axis_type, "data": categories, "axisLabel": {"fontSize": 11}},
            "series": [{
                "type": "bar",
                "data": values,
                "label": {"show": True, "position": "right",
                          "fontSize": 11, "color": "#374151"},
                "itemStyle": {"color": color},
            }],
        }
    else:
        option = {
            "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {**DEFAULT_TOOLTIP},
            "grid": DEFAULT_GRID,
            "xAxis": {"type": axis_type, "data": categories,
                      "axisLabel": {"rotate": 30 if len(categories) > 6 else 0, "fontSize": 11}},
            "yAxis": {"type": "value"},
            "series": [{
                "type": "bar",
                "data": values,
                "label": {"show": True, "position": "top", "fontSize": 11, "color": "#374151"},
                "itemStyle": {"color": color},
            }],
        }
    st_echarts(option, height=f"{height}px", key=key)


def grouped_bar(categories, series_list, title="", height=400, key=None):
    """
    Grouped bar chart. series_list = [{"name": str, "data": list, "color": str}, ...]
    """
    series = []
    for s in series_list:
        series.append({
            "name": s["name"],
            "type": "bar",
            "data": s["data"],
            "label": {"show": True, "position": "top", "fontSize": 10, "color": "#374151"},
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
    series = []
    for s in series_list:
        series.append({
            "name": s["name"],
            "type": "bar",
            "stack": "total",
            "data": s["data"],
            "label": {"show": True, "position": "inside", "fontSize": 10, "color": "#fff"},
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
    series = []
    for s in series_list:
        entry = {
            "name": s["name"],
            "type": "line",
            "data": s["data"],
            "label": {"show": len(s["data"]) <= 15, "position": "top",
                      "fontSize": 10, "color": "#374151"},
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
                "name": bar_name, "type": "bar", "data": bar_series,
                "label": {"show": True, "position": "top", "fontSize": 10, "color": "#374151"},
                "itemStyle": {"color": bar_color},
            },
            {
                "name": line_name, "type": "line", "yAxisIndex": 1, "data": line_series,
                "label": {"show": True, "position": "top", "fontSize": 10, "color": "#374151"},
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
            "label": {"show": True, "position": "right", "fontSize": 10,
                      "formatter": lambda p: group["data"][p["dataIndex"]][3] if p["dataIndex"] < len(group["data"]) else ""},
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
    if height is None:
        height = max(350, len(categories) * 28)
    item_colors = colors if colors else [PALETTE[0]] * len(values)
    option = {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {**DEFAULT_TOOLTIP, "trigger": "axis"},
        "grid": {"left": "25%", "right": "12%", "bottom": "8%", "top": "12%"},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "category", "data": categories, "axisLabel": {"fontSize": 11}},
        "series": [{
            "type": "bar",
            "data": [{"value": v, "itemStyle": {"color": c}} for v, c in zip(values, item_colors)],
            "label": {"show": True, "position": "right", "fontSize": 11, "color": "#374151"},
        }],
    }
    st_echarts(option, height=f"{height}px", key=key)


def gauge_chart(value, title="", max_val=100, thresholds=None, height=250, key=None):
    """Gauge chart for single KPI."""
    if thresholds is None:
        thresholds = [[0.3, "#dc2626"], [0.7, "#d97706"], [1, "#16a34a"]]
    option = {
        "series": [{
            "type": "gauge",
            "startAngle": 200, "endAngle": -20,
            "min": 0, "max": max_val,
            "axisLine": {"lineStyle": {"width": 20, "color": thresholds}},
            "pointer": {"width": 5},
            "title": {"text": title, "offsetCenter": [0, "80%"], "fontSize": 13},
            "detail": {"formatter": f"{value:.1f}", "fontSize": 22, "offsetCenter": [0, "50%"]},
            "data": [{"value": value}],
        }],
    }
    st_echarts(option, height=f"{height}px", key=key)
